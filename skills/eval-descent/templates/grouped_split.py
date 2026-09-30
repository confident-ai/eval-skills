"""Deterministic group-disjoint splits. Review class/task coverage before freezing."""
import hashlib
import math
NAMES = ('development', 'validation', 'test')
def grouped_split(records, fractions=(.4,.3,.3), seed=7):
    if len(fractions)!=3 or any(not math.isfinite(f) or f<=0 for f in fractions):
        raise ValueError('three positive finite fractions required')
    groups={}; seen=set()
    for row in records:
        i=row['id']
        if i in seen: raise ValueError('duplicate case ID')
        seen.add(i)
        group=str(row.get('group_id') or row.get('thread_id') or i)
        groups.setdefault(group,[]).append(i)
    if len(groups)<3: raise ValueError('at least three independent groups are required')
    order=sorted(groups,key=lambda g:hashlib.sha256(f'{seed}:{g}'.encode()).hexdigest())
    total=sum(fractions); targets=[len(groups)*f/total for f in fractions]; counts=[0,0,0]
    out={n:[] for n in NAMES}
    for index,g in enumerate(order):
        slot=index if index<3 else max(range(3),key=lambda i:targets[i]-counts[i])
        counts[slot]+=1;out[NAMES[slot]].extend(groups[g])
    return {k:sorted(v) for k,v in out.items()}
