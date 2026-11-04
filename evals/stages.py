"""Cheap catalogue/retrieval benchmark; classifier runs are explicit and live."""
import argparse
import json
import time
from agent.policies import PolicyStore, load_policies, evaluate_policy, configured_store
from agent.classifier import classify


def benchmark(records, sizes=(10,100,1000), store_factory=None):
    rows=[]
    examples=[(p,t) for p in records for t in p['tests']]
    for size in sizes:
        # Always retain all real records; sizes refer to added synthetic distractors.
        distractors=[{'id':f'synthetic-{i}','version':1,'topic':'prohibited_items','text':f'Synthetic calibration component ZX{i} requires review.', 'aliases':[f'ZX{i}'],'active':True,'tests':[]} for i in range(size)]
        store=store_factory(records+distractors) if store_factory else PolicyStore(records+distractors)
        found=correct=0
        start=time.perf_counter()
        for p,t in examples:
            hits=store.search(t['query'],p['topic'],5)
            found += p['id'] in {h['id'] for h in hits}
            correct += evaluate_policy(p,t['facts'])['outcome']==t['expected']
        rows.append({'policies':len(records)+size,'synthetic_distractors':size,'queries':len(examples),'recall_at_5':found/max(1,len(examples)),'oracle_rule_accuracy':correct/max(1,len(examples)),'latency_ms':round((time.perf_counter()-start)*1000,2),'retrieval_mode':'lexical+aliases' if store.embed is None else 'hybrid_embeddings'})
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--classifier',action='store_true')
    parser.add_argument('--semantic',action='store_true')
    args=parser.parse_args()
    failed=False
    if args.classifier:
        counts={name:{'tp':0,'fp':0,'fn':0} for name in ['harmful','injection']}
        total=correct=0
        from pathlib import Path
        from evals.run import validate_cases
        cases=[json.loads(line) for line in (Path(__file__).parent/'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        validate_cases(cases)
        for case in cases:
            try:
                route,_=classify(case['input'])
                expected=case.get('classification',{})
                passed=all(route.get(k)==v for k,v in expected.items()) and bool(expected)
                for name, values in counts.items():
                    if name in expected:
                        predicted,actual=route[name],expected[name]
                        values['tp']+=bool(predicted and actual)
                        values['fp']+=bool(predicted and not actual)
                        values['fn']+=bool(not predicted and actual)
            except Exception:
                passed=False
            total+=1
            correct+=passed
            failed |= not passed
            print(json.dumps({'id':case['id'],'passed':passed}))
        print(json.dumps({'classification_accuracy':correct/max(1,total),'risk_counts':counts}))
    else:
        records=load_policies()
        store=configured_store() if args.semantic else None
        if args.semantic and store.embed is None:
            parser.error('Set EMBEDDING_MODEL for semantic benchmarking')
        # Synthetic distractors have no embeddings here: do not mislabel this as
        # a semantic scaling test. A proper semantic run indexes every record.
        factory=None
        if store:
            from agent.policies import build_index
            from pathlib import Path
            factory=lambda records: PolicyStore(records,store.embed,build_index(records,path=Path('.cache/benchmark-index.json'),embed=store.embed,model=store.embedding_model))
        for row in benchmark(records,store_factory=factory):
            print(json.dumps(row))
            failed |= row['recall_at_5']<1 or row['rule_accuracy']<1
    raise SystemExit(1 if failed else 0)


if __name__=='__main__': main()
