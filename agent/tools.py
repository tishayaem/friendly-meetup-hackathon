"""Tools with server-owned authorisation. Model arguments never grant access."""
import json
from pathlib import Path
from agent.policies import PolicyStore, evaluate_policy, explicit_facts, runtime_policy

DATA = Path(__file__).parent / 'data'
ORDERS = {o['order_id']: o for o in json.loads((DATA/'orders.json').read_text(encoding='utf-8'))}
PUBLIC_FIELDS = {'order_id','service','status','ordered','expected_delivery','delivered','weight_kg','pigeon_protect'}


def get_order(order_id: str, *, session=None) -> str:
    order_id = order_id.strip().upper()
    if session is None or not session.authorised(order_id):
        return json.dumps({'error':'verification_required'})
    order = ORDERS.get(order_id)
    return json.dumps({k:v for k,v in order.items() if k in PUBLIC_FIELDS}) if order else json.dumps({'error':'order_not_found'})


def search_policies(query: str) -> str:
    return json.dumps([runtime_policy(p) for p in PolicyStore().search(query)], ensure_ascii=False)


class ToolController:
    def __init__(self, session, store, policy_ids, question=''):
        self.session, self.store, self.policy_ids = session, store, set(policy_ids)
        self.facts = explicit_facts(question)

    def execute(self, name, args):
        if not isinstance(args, dict):
            raise ValueError('Tool arguments must be an object')
        if name == 'get_order' and set(args) == {'order_id'} and isinstance(args['order_id'], str):
            return json.loads(get_order(args['order_id'], session=self.session))
        if name == 'search_policies' and set(args) == {'query'} and isinstance(args['query'], str):
            policies = self.store.search(args['query'])
            self.policy_ids.update(p['id'] for p in policies)
            return [runtime_policy(p) for p in policies]
        if name == 'evaluate_policy' and set(args) == {'policy_id','facts'} and isinstance(args['facts'],dict):
            if args['policy_id'] not in self.policy_ids:
                raise ValueError('Policy must be retrieved first')
            policy = next(p for p in self.store.records if p['id'] == args['policy_id'])
            if any(self.facts.get(k) != v or type(v) not in (int, float, bool) for k,v in args['facts'].items()):
                raise ValueError('Rule facts are not grounded in the request')
            return evaluate_policy(policy, args['facts'])
        raise ValueError('Unknown tool or invalid arguments')


def schema(name, description, properties):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}}}

TOOL_SCHEMAS = [
    schema('get_order','Read permitted fields of an order, only after server verification.',{'order_id':{'type':'string'}}),
    schema('search_policies','Find current policy records; similarity is not permission or a prohibition.',{'query':{'type':'string'}}),
    schema('evaluate_policy','Evaluate a retrieved rule. Facts must be supported by user input or tools; do not invent missing fields.',{'policy_id':{'type':'string'},'facts':{'type':'object'}}),
]
