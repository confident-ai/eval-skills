import { createHash } from 'node:crypto';
/** Deterministic group-disjoint splits, stratified when records carry a `stratum`; identical partitions to grouped_split.py. */
export function groupedSplit(records: {id:string;group_id?:unknown;thread_id?:unknown;stratum?:string|null}[], fractions=[.4,.3,.3], seed=7): Record<string,string[]> {
  if(fractions.length!==3 || fractions.some(f=>!Number.isFinite(f)||f<=0))throw new Error('three positive finite fractions required');
  const names=['development','validation','test']; const groups=new Map<string,string[]>(); const seen=new Set<string>(); const strata=new Map<string,Map<string,number>>();
  const stratified=records.some(row=>row.stratum!==undefined&&row.stratum!==null);
  for(const row of records){if(seen.has(row.id))throw new Error('duplicate case ID');seen.add(row.id);const g=String(row.group_id||row.thread_id||row.id);groups.set(g,[...(groups.get(g)||[]),row.id]);
    if(stratified){const s=row.stratum!==undefined&&row.stratum!==null?String(row.stratum):'';const c=strata.get(g)||new Map<string,number>();c.set(s,(c.get(s)||0)+1);strata.set(g,c);}}
  if(groups.size<3)throw new Error('at least three independent groups are required');
  const hash=(g:string)=>createHash('sha256').update(`${seed}:${g}`).digest('hex');
  const total=fractions.reduce((a,b)=>a+b,0);
  const out:Record<string,string[]>={development:[],validation:[],test:[]};
  if(!stratified){
    const order=[...groups.keys()].sort((a,b)=>hash(a).localeCompare(hash(b)));
    const targets=fractions.map(f=>groups.size*f/total), counts=[0,0,0];
    order.forEach((g,index)=>{let slot=index;if(index>=3){slot=0;for(let i=1;i<3;i++)if(targets[i]!-counts[i]!>targets[slot]!-counts[slot]!)slot=i;}counts[slot]!++;out[names[slot]!]!.push(...groups.get(g)!);});
    for(const ids of Object.values(out))ids.sort();return out;
  }
  // Stratified (same rules as grouped_split.py): pool strata found in fewer than three groups, add an
  // all-cases stratum, place the rarest strata (then larger groups) first, prefer a split still missing one of the group's
  // strata, and pick the split with the smallest increase in squared share error; fill empty splits last.
  const spread=new Map<string,number>();
  for(const c of strata.values())for(const s of c.keys())spread.set(s,(spread.get(s)||0)+1);
  for(const [g,c] of strata){const pooled=new Map<string,number>([['a',[...c.values()].reduce((a,b)=>a+b,0)]]);
    for(const [s,k] of c){const key=spread.get(s)!>=3?'s:'+s:'r';pooled.set(key,(pooled.get(key)||0)+k);}strata.set(g,pooled);}
  const keys=[...new Set([...strata.values()].flatMap(c=>[...c.keys()]))].sort();
  const size=new Map(keys.map(s=>[s,[...strata.values()].reduce((a,c)=>a+(c.get(s)||0),0)]));
  const rarity=(g:string)=>Math.min(...[...strata.get(g)!.keys()].map(s=>size.get(s)!));
  const hashes=new Map([...groups.keys()].map(g=>[g,hash(g)]));
  const order=[...groups.keys()].sort((a,b)=>rarity(a)-rarity(b)||strata.get(b)!.get('a')!-strata.get(a)!.get('a')!||(hashes.get(a)!<hashes.get(b)!?-1:hashes.get(a)!>hashes.get(b)!?1:0));
  const filled=[0,1,2].map(()=>new Map(keys.map(s=>[s,0])));
  order.forEach((g,index)=>{
    const empty=[0,1,2].filter(i=>out[names[i]!]!.length===0);
    const missing=[0,1,2].filter(i=>[...strata.get(g)!.keys()].some(s=>s.startsWith('s:')&&filled[i]!.get(s)===0));
    let slot=-1,best=0;
    for(const i of (order.length-index<=empty.length?empty:missing.length?missing:[0,1,2])){
      let cost=0;
      for(const s of keys){const c=strata.get(g)!.get(s);if(c!==undefined){const n=size.get(s)!;cost+=c*(c+2*(filled[i]!.get(s)!-n*fractions[i]!/total))/(n*n);}}
      if(slot<0||cost<best){slot=i;best=cost;}
    }
    for(const [s,c] of strata.get(g)!)filled[slot]!.set(s,filled[slot]!.get(s)!+c);
    out[names[slot]!]!.push(...groups.get(g)!);
  });
  for(const ids of Object.values(out))ids.sort();return out;
}
