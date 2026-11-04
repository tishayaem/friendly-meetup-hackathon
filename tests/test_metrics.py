import pytest
from evals.metrics import summarize, distribution, grouped_scorecards


def test_unknown_assessments_are_not_zero_hallucinations():
    s=summarize([{'passed':True,'result':{'latency_s':1,'tokens':100}}])
    assert s['decision_accuracy']['rate'] is None
    assert s['unsupported_answer_rate']['rate'] is None
    assert s['critical_violations']['incidents'] is None
    assert s['limitations']


def test_scorecard_rates_and_role_cost_separation():
    rows=[{'experiment':{'arm':'workflow','snapshot':'S0'},'passed':True,'result':{},'timing':{'runtime_ms':100},'assessment':{'decision_correct':True,'answered':True,'unsupported_answer':False,'answerable':True,'useful_correct_answer':True,'critical_violations':[]},'calls':[{'role':'agent','prompt_tokens':10,'completion_tokens':5,'api_cost':.01,'currency':'GBP'},{'role':'judge','prompt_tokens':20,'completion_tokens':5}]}]
    s=summarize(rows)
    assert s['decision_accuracy']['rate']==1
    assert s['critical_violations']['incidents']==0
    assert s['api_usage_by_role']['agent']['api_cost']==.01
    assert s['api_usage_by_role']['judge']['api_cost'] is None
    assert grouped_scorecards(rows)[0]['arm']=='workflow'


def test_refusal_cannot_game_useful_coverage():
    s=summarize([{'assessment':{'answered':False,'answerable':True,'useful_correct_answer':False}}])
    assert s['unsupported_answer_rate']['rate'] is None
    assert s['useful_response_coverage']['rate']==0


def test_percentiles_and_conversation_accounting():
    assert distribution([1,2,3,4])=={'n':4,'median':2.5,'p95':4}
    s=summarize([{'case':{'steps':[{},{}]},'result':{'latency_s':1}}])
    assert s['runtime_ms']['n']==0
    assert any('multi-turn' in x for x in s['limitations'])


def test_gold_examples_never_reach_tools_or_agent():
    from agent.policies import PolicyStore, runtime_policy
    from agent.tools import ToolController
    from agent.verification import Session
    store=PolicyStore()
    assert any(p['tests'] for p in store.records)
    assert all('tests' not in runtime_policy(p) for p in store.records)
    rows=ToolController(Session(),store,[]).execute('search_policies',{'query':'perfume'})
    assert all('tests' not in p for p in rows)


def test_model_prompt_does_not_contain_development_tests():
    from tests.test_pipeline import Client, Message, routing
    from agent.agent import run_agent
    from agent.policies import PolicyStore
    client=Client(Message('Next Day costs £6.50.'))
    result=run_agent('price',classifier=routing(),store=PolicyStore(),client=client,model='fake')
    assert result['outcome']=='answered'
    import json
    evidence_message=client.requests[0]['messages'][1]['content']
    evidence=json.loads(evidence_message.split(': ',1)[1])
    assert all('tests' not in p for p in evidence['policies'])


def test_addition_fixture_is_valid_and_separate():
    from pathlib import Path
    from agent.policies import load_policies, evaluate_policy
    additions=load_policies(Path('evals/fixtures/policy_additions.json'))
    active=load_policies()
    assert not {p['id'] for p in additions}&{p['id'] for p in active}
    for p in additions:
        for case in p['tests']:
            assert evaluate_policy(p,case['facts'])['outcome']==case['expected']

def test_claude_compatibility_does_not_send_unsupported_parameters():
    from agent.llm import completion_options
    from types import SimpleNamespace
    assert completion_options(SimpleNamespace(base_url='https://api.anthropic.com/v1/'),json_output=True)=={}
    assert completion_options(SimpleNamespace(base_url='http://localhost:11434/v1'),json_output=True)=={'temperature':0,'response_format':{'type':'json_object'}}
