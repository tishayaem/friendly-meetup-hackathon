"""Offline scorecards. Missing measurements stay unknown, never become zero cost/risk.

Usage: uv run python -m evals.metrics results/RUN.jsonl
Future benchmark rows may add assessment, timing and per-call usage records;
legacy runner rows remain readable with explicit measurement limitations.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def rate(values):
    scored=[v for v in values if type(v) is bool]
    return {'numerator':sum(scored),'denominator':len(scored),'rate':sum(scored)/len(scored) if scored else None}


def distribution(values):
    values=sorted(v for v in values if type(v) in (int,float) and math.isfinite(v) and v>=0)
    if not values: return {'n':0,'median':None,'p95':None}
    n=len(values)
    median=values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
    return {'n':n,'median':median,'p95':values[max(0,math.ceil(.95*n)-1)]}


def summarize(rows):
    assessments=[r.get('assessment',{}) for r in rows]
    latency=[]
    calls=[]
    limitations=set()
    for row in rows:
        if 'runtime_ms' in row.get('timing',{}):
            latency.append(row['timing']['runtime_ms'])
        elif len(row.get('case',{}).get('steps',[]))<=1:
            seconds=row.get('result',{}).get('latency_s')
            if seconds is not None: latency.append(seconds*1000)
        else:
            limitations.add('Legacy multi-turn latency excluded: final-turn timing is not conversation timing.')
        if 'calls' in row:
            calls.extend(row['calls'])
        else:
            limitations.add('Per-call token/cost data missing; legacy total tokens excludes embeddings/judge and can omit earlier turns.')
    by_role=defaultdict(lambda:{'calls':0,'prompt_tokens':0,'completion_tokens':0,'tokens_unknown':0,'api_cost':0.,'cost_unknown':0})
    currencies=set()
    for call in calls:
        role=by_role[call['role']]
        role['calls']+=1
        for key in ['prompt_tokens','completion_tokens']:
            if type(call.get(key)) is int and call[key]>=0: role[key]+=call[key]
            else: role['tokens_unknown']+=1
        if type(call.get('api_cost')) in (int,float) and call['api_cost']>=0 and call.get('currency'):
            role['api_cost']+=call['api_cost']; currencies.add(call['currency'])
        else: role['cost_unknown']+=1
    for role in by_role.values():
        if role['cost_unknown'] or len(currencies)>1: role['api_cost']=None
    if len(currencies)>1: limitations.add('Mixed currencies: costs cannot be summed.')
    critical=[a['critical_violations'] for a in assessments if isinstance(a.get('critical_violations'),list)]
    return {
        'cases':len(rows),
        'suite_pass':rate([r.get('passed') for r in rows]),
        'decision_accuracy':rate([a.get('decision_correct') for a in assessments]),
        'unsupported_answer_rate':rate([a.get('unsupported_answer') for a in assessments if a.get('answered') is True]),
        'useful_response_coverage':rate([a.get('useful_correct_answer') for a in assessments if a.get('answerable') is True]),
        'critical_violations':{'incidents':sum(len(x) for x in critical) if critical else None,'assessed_cases':len(critical)},
        'runtime_ms':distribution(latency),
        'api_usage_by_role':dict(by_role),
        'currency':next(iter(currencies)) if len(currencies)==1 else None,
        'runtime_error_rate':rate([bool(r.get('result',{}).get('error')) for r in rows]),
        'assessment_coverage':rate([bool(a) for a in assessments]),
        'limitations':sorted(limitations),
    }


def grouped_scorecards(rows):
    groups=defaultdict(list)
    for row in rows:
        experiment=row.get('experiment',{})
        groups[(experiment.get('arm','legacy'),experiment.get('snapshot','unspecified'))].append(row)
    return [{'arm':arm,'snapshot':snapshot,**summarize(items)} for (arm,snapshot),items in sorted(groups.items())]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('runs',nargs='+',type=Path)
    args=parser.parse_args()
    rows=[]
    for path in args.runs:
        rows.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    print(json.dumps(grouped_scorecards(rows),indent=2))


if __name__=='__main__': main()
