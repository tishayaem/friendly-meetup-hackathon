import json
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from agent.agent import run_agent
from agent.classifier import classify
from agent.decisions import refund_decision, validate_answer
from agent.policies import PolicyStore, build_index, evaluate_policy, load_policies
from agent.tools import ToolController, get_order
from agent.verification import Session
from evals.run import validate_cases


def routing(intent='policy', topics=None, route='support', harmful=False):
    return lambda q: ({'route':route,'intent':intent,'topics':topics or ['pricing'],'harmful':harmful,'injection':False,'suggested_tools':[]},0)


class Message:
    def __init__(self,content='',tool_calls=None):
        self.content,self.tool_calls=content,tool_calls or []
    def model_dump(self,**kw):
        return {'role':'assistant','content':self.content,'tool_calls':[{'id':c.id,'type':'function','function':{'name':c.function.name,'arguments':c.function.arguments}} for c in self.tool_calls]}


class Client:
    def __init__(self,*messages):
        self.messages=iter(messages)
        self.chat=NS(completions=NS(create=self.create))
        self.requests=[]
    def create(self,**kwargs):
        self.requests.append(deepcopy(kwargs))
        return NS(choices=[NS(message=next(self.messages))],usage=NS(total_tokens=1))


def call(name,args):
    return NS(id='call-1',function=NS(name=name,arguments=json.dumps(args)))


@pytest.fixture
def session():
    return Session(code_factory=lambda:'123456')


def test_verification_binding_expiry_replay():
    now=[0]
    s=Session(clock=lambda:now[0],code_factory=lambda:'123456')
    assert s.start('pp-1003')=='123456'
    assert not s.authorised('PP-1003')
    assert s.verify('123456')
    assert not s.verify('123456')
    assert s.authorised('PP-1003') and not s.authorised('PP-1004')
    assert not Session().authorised('PP-1003')
    now[0]=300
    assert not s.authorised('PP-1003')


def test_attempts_and_expired_code(session):
    session.start('PP-1003')
    for _ in range(3): assert not session.verify('wrong')
    assert session.state=='verification_failed'
    assert not session.verify('123456')
    s=Session(clock=lambda:0)
    s.start('PP-1003'); s.expires=0
    assert not s.verify('anything')
    assert s.state=='verification_expired'


def test_tool_authorisation_at_source(session):
    assert json.loads(get_order('PP-1003'))=={'error':'verification_required'}
    session.start('PP-1003'); session.verify('123456')
    data=json.loads(get_order('PP-1003',session=session))
    assert data['status']=='in transit'
    assert not {'customer_name','address','phone'} & data.keys()
    assert 'error' in json.loads(get_order('PP-1004',session=session))
    c=ToolController(session,PolicyStore(),[])
    with pytest.raises(ValueError): c.execute('get_order',{'order_id':'PP-1004','verified':True})
    with pytest.raises(ValueError): c.execute('issue_refund',{})
    with pytest.raises(ValueError): c.execute('evaluate_policy',{'policy_id':'prohibited-cash','facts':{}})


@pytest.mark.parametrize('p,t',[(p,t) for p in load_policies() for t in p['tests']])
def test_reviewed_policy_examples(p,t):
    assert p['id'] in [r['id'] for r in PolicyStore().search(t['query'],p['topic'])]
    assert evaluate_policy(p,t['facts'])['outcome']==t['expected']


def test_retrieval_no_match_inactive_and_similarity():
    store=PolicyStore()
    assert not store.search('ceramic mug','prohibited_items')
    assert not store.search('moisturiser','prohibited_items')
    assert 'prohibited-perfume' in [p['id'] for p in store.search('cologne','prohibited_items')]
    p=deepcopy(store.records[-1]); p['active']=False
    assert not PolicyStore([p]).search(p['text'])
    assert all('~~' not in p['text'] for p in store.records)


def test_incremental_index_and_semantic_retrieval(tmp_path):
    p=deepcopy(load_policies()[-1]); calls=[]
    def embed(text): calls.append(text); return [1.,0.]
    path=tmp_path/'index.json'
    entries=build_index([p],path,embed,'fake')
    build_index([p],path,embed,'fake')
    assert len(calls)==1
    assert PolicyStore([p],embed,entries).search('unseen paraphrase')[0]['id']==p['id']
    p['version']+=1
    build_index([p],path,embed,'fake')
    assert len(calls)==3
    assert build_index([],path,embed,'fake')=={}


@pytest.mark.parametrize('service,delivered,days,arrival,expected',[
 ('Next Day','2026-11-03',None,None,'ineligible'),
 ('Next Day','2026-11-04',None,None,'eligible_to_claim'),
 ('Same Day','2026-11-04',None,None,'eligible_to_claim'),
 ('Same Day','2026-11-03',None,None,'needs_information'),
 ('Same Day','2026-11-03',None,'21:00','ineligible'),
 ('Same Day','2026-11-03',None,'21:01','eligible_to_claim'),
 ('Standard','2026-11-03',None,None,'ineligible'),
 ('Standard','2026-11-06',None,None,'needs_information'),
 ('Standard','2026-11-06',2,None,'ineligible'),
 ('Standard','2026-11-06',3,None,'eligible_to_claim'),
])
def test_refunds(service,delivered,days,arrival,expected):
    assert refund_decision({'service':service,'expected_delivery':'2026-11-03','delivered':delivered},working_days_late=days,arrival_time=arrival)['outcome']==expected


@pytest.mark.parametrize('data',[
 {}, {'route':'bad'}, {'route':'support','intent':'policy','harmful':'false'},
])
def test_classifier_rejects_invalid_json_contract(data):
    with pytest.raises((ValueError,TypeError)):
        classify('Hello',Client(Message(json.dumps(data))),'fake')


def test_classifier_valid():
    data=routing()('x')[0]
    assert classify('x',Client(Message(json.dumps(data))),'fake')[0]==data


def test_input_routing_and_classifier_failure():
    assert run_agent('bad',classifier=routing(route='refuse',harmful=True))['outcome']=='refused'
    assert run_agent('cats',classifier=routing(route='irrelevant'))['outcome']=='irrelevant'
    def broken(q): raise ValueError()
    assert run_agent('x',classifier=broken)['outcome']=='clarify'
    assert run_agent('address PP-1003',classifier=routing(intent='personal_data'))['tool_calls']==[]


def test_pending_then_resume(session):
    first=run_agent('Where is PP-1003?',session=session,classifier=routing('order'))
    assert first['outcome']=='needs_verification' and not first['tool_calls']
    session.start('PP-1003'); session.verify('123456')
    client=Client(Message('Your parcel is in transit.'))
    second=run_agent('Where is PP-1003?',session=session,classifier=routing('order',[]),store=PolicyStore(),client=client,model='fake')
    assert second['outcome']=='answered'
    assert not any(p in json.dumps(client.requests) for p in ['Priya Nair','Castle Street','123456'])


def test_model_cannot_bypass_tools(session):
    client=Client(Message(tool_calls=[call('get_order',{'order_id':'PP-1003'})]),Message('Please verify your order.'))
    result=run_agent('price',session=session,classifier=routing(),store=PolicyStore(),client=client,model='fake')
    assert result['tool_calls'][0]['status']=='denied'
    assert 'Priya Nair' not in json.dumps(client.requests)


def test_repair_once_and_fallback():
    client=Client(Message('It costs 99999 pounds.'),Message('It costs 99999 pounds.'))
    result=run_agent('price',classifier=routing(),store=PolicyStore(),client=client,model='fake')
    assert result['outcome']=='validation_failed' and result['attempts']==2
    assert len(client.requests)==2
    assert 'unsupported_number' in client.requests[1]['messages'][-1]['content']


def test_successful_repair():
    client=Client(Message('It costs 99999 pounds.'),Message('Next Day costs £6.50.'))
    result=run_agent('price',classifier=routing(),store=PolicyStore(),client=client,model='fake')
    assert result['outcome']=='answered' and result['attempts']==2


def test_tool_budget_and_unknown_tool():
    client=Client(Message(tool_calls=[call('delete_orders',{})]))
    r=run_agent('price',max_steps=1,classifier=routing(),store=PolicyStore(),client=client,model='fake')
    assert r['outcome']=='tool_budget_exhausted'
    assert r['tool_calls'][0]['status']=='denied'


def test_validator_detects_known_bad_answers():
    assert 'unsupported_action_claim' in validate_answer('I have issued your refund.',evidence={})
    assert 'personal_data' in validate_answer('The customer is Priya Nair.',evidence={})
    assert validate_answer('Next Day costs £6.50.',evidence={'price':'6.50'})==[]


def test_case_validation():
    cases=[json.loads(line) for line in (__import__('pathlib').Path('evals/cases.jsonl')).read_text(encoding='utf-8').splitlines()]
    assert len(cases)==30
    validate_cases(cases)
    with pytest.raises(ValueError): validate_cases(cases+[cases[0]])
    cases[0]['checks']=[{'type':'unknown'}]
    with pytest.raises(ValueError): validate_cases(cases)


def test_judge_validation(monkeypatch):
    import evals.judge as module
    monkeypatch.setattr(module,'client_for',lambda role:(Client(Message('{"score":4,"reason":"Correct"}')),'fake'))
    assert module.judge({'input':'x','expected':'y'},{'answer':'z'})['passed']
    monkeypatch.setattr(module,'client_for',lambda role:(Client(Message('{"score":8,"reason":"x"}')),'fake'))
    with pytest.raises(ValueError): module.judge({'input':'x','expected':'y'},{'answer':'z'})

def test_fact_grounding_and_deterministic_item_decision(session):
    store=PolicyStore()
    c=ToolController(session,store,['prohibited-perfume'],'Can I send 100 ml perfume?')
    with pytest.raises(ValueError):
        c.execute('evaluate_policy',{'policy_id':'prohibited-perfume','facts':{'volume_ml':150}})
    assert c.execute('evaluate_policy',{'policy_id':'prohibited-perfume','facts':{'volume_ml':100}})['outcome']=='not_prohibited_by_rule'
    for n,expected in [(100,'not_prohibited_by_rule'),(101,'prohibited')]:
        r=run_agent(f'Can I send {n} ml perfume?',classifier=routing(topics=['prohibited_items']),store=store)
        assert r['decisions'][0]['outcome']==expected
        assert r['attempts']==0
    r=run_agent('Can I send cologne?',classifier=routing(topics=['prohibited_items']),store=store)
    assert r['decisions'][0]['outcome']=='needs_information'


def test_new_policy_data_adds_retrieval_and_rule_tests(tmp_path):
    from agent.policies import load_policies
    p={'id':'synthetic-fuel','version':1,'topic':'prohibited_items','active':True,'text':'Synthetic test fuel over 20 ml is prohibited.','aliases':['test fuel'],'rule':{'required':['volume_ml'],'conditions':[{'field':'volume_ml','op':'gt','value':20}],'outcome':'prohibited'},'tests':[{'query':'Can I ship 21 ml test fuel?','facts':{'volume_ml':21},'expected':'prohibited'}]}
    path=tmp_path/'catalogue.json'; path.write_text(json.dumps([p]),encoding='utf-8')
    store=PolicyStore(load_policies(path))
    assert store.search('Can I ship 21 ml test fuel?')[0]['id']==p['id']
    for case in p['tests']: assert evaluate_policy(p,case['facts'])['outcome']==case['expected']


def test_evaluation_failures_do_not_disappear(monkeypatch):
    import evals.run as module
    monkeypatch.setattr(module,'run_agent',lambda *a,**k:{'answer':'x','tool_calls':[],'latency_s':0,'tokens':0})
    def broken(*a): raise ValueError('Invalid verdict')
    monkeypatch.setattr(module,'judge',broken)
    r=module.evaluate({'id':'x','input':'q','expected':'a','checks':[]},True)
    assert r['passed'] is False and r['judge']['error']

def test_invalid_fact_types_do_not_imply_allowed():
    perfume=next(p for p in load_policies() if p['id']=='prohibited-perfume')
    assert evaluate_policy(perfume,{'volume_ml':'a lot'})['outcome']=='needs_information'


def test_negation_does_not_prohibit_wrong_item():
    r=run_agent('Can I send vouchers, not cash?',classifier=routing(topics=['prohibited_items']),store=PolicyStore())
    assert r['outcome']=='needs_information'


def test_compare_retains_repetitions(tmp_path):
    from evals.compare import load
    path=tmp_path/'run.jsonl'
    path.write_text('\n'.join(json.dumps({'case':{'id':'a'},'repetition':i}) for i in [1,2]),encoding='utf-8')
    assert len(load(path))==2


def test_catalogue_requires_examples_and_valid_aliases(tmp_path):
    p=deepcopy(load_policies()[-1]); p['tests']=[]
    path=tmp_path/'bad.json'; path.write_text(json.dumps([p]),encoding='utf-8')
    with pytest.raises(ValueError): load_policies(path)
