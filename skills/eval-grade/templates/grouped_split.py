"""Deterministic group-disjoint splits, stratified when records carry a string `stratum`. Review class/task coverage before freezing."""
import hashlib
import math
NAMES = ('development', 'validation', 'test')
def grouped_split(records, fractions=(.4,.3,.3), seed=7):
    if len(fractions)!=3 or any(not math.isfinite(f) or f<=0 for f in fractions):
        raise ValueError('three positive finite fractions required')
    groups={}; seen=set(); strata={}
    stratified=any(row.get('stratum') is not None for row in records)
    for row in records:
        i=row['id']
        if i in seen: raise ValueError('duplicate case ID')
        seen.add(i)
        group=str(row.get('group_id') or row.get('thread_id') or i)
        groups.setdefault(group,[]).append(i)
        if stratified:
            s=str(row['stratum']) if row.get('stratum') is not None else ''
            strata.setdefault(group,{}); strata[group][s]=strata[group].get(s,0)+1
    if len(groups)<3: raise ValueError('at least three independent groups are required')
    hash_of=lambda g:hashlib.sha256(f'{seed}:{g}'.encode()).hexdigest()
    total=sum(fractions)
    out={n:[] for n in NAMES}
    if not stratified:
        order=sorted(groups,key=hash_of)
        targets=[len(groups)*f/total for f in fractions]; counts=[0,0,0]
        for index,g in enumerate(order):
            slot=index if index<3 else max(range(3),key=lambda i:targets[i]-counts[i])
            counts[slot]+=1;out[NAMES[slot]].extend(groups[g])
        return {k:sorted(v) for k,v in out.items()}
    # Stratified. Strata found in fewer than three groups cannot reach every split, so they are pooled,
    # and an all-cases stratum keeps split sizes on target. Groups holding the rarest strata go first,
    # larger groups before smaller ones.
    # A group goes to a split still missing one of its strata when there is one (so every stratum that
    # spans three groups appears in every split), choosing the split where it least increases the
    # squared gap between each stratum's share and its target share: one case of a rare label weighs
    # more than one of a common label. The last groups fill any split still empty.
    spread={}
    for c in strata.values():
        for s in c: spread[s]=spread.get(s,0)+1
    for g,c in strata.items():
        pooled={'a':sum(c.values())}
        for s,k in c.items():
            key='s:'+s if spread[s]>=3 else 'r'; pooled[key]=pooled.get(key,0)+k
        strata[g]=pooled
    keys=sorted({s for c in strata.values() for s in c})
    size={s:sum(c.get(s,0) for c in strata.values()) for s in keys}
    order=sorted(groups,key=lambda g:(min(size[s] for s in strata[g]),-strata[g]['a'],hash_of(g)))
    filled=[{s:0 for s in keys} for _ in range(3)]
    for index,g in enumerate(order):
        empty=[i for i in range(3) if not out[NAMES[i]]]
        missing=[i for i in range(3) if any(filled[i][s]==0 for s in strata[g] if s.startswith('s:'))]
        slot=-1;best=0.0
        for i in (empty if len(order)-index<=len(empty) else missing or range(3)):
            cost=0.0
            for s in keys:
                if s in strata[g]:
                    c=strata[g][s]; cost+=c*(c+2*(filled[i][s]-size[s]*fractions[i]/total))/(size[s]*size[s])
            if slot<0 or cost<best: slot=i;best=cost
        for s,c in strata[g].items(): filled[slot][s]+=c
        out[NAMES[slot]].extend(groups[g])
    return {k:sorted(v) for k,v in out.items()}
