import { createHash } from 'node:crypto';
export function groupedSplit(records: {id:string;group_id?:unknown;thread_id?:unknown}[], fractions=[.4,.3,.3], seed=7): Record<string,string[]> {
  if(fractions.length!==3 || fractions.some(f=>!Number.isFinite(f)||f<=0))throw new Error('three positive finite fractions required');
  const names=['development','validation','test']; const groups=new Map<string,string[]>(); const seen=new Set<string>();
  for(const row of records){if(seen.has(row.id))throw new Error('duplicate case ID');seen.add(row.id);const g=String(row.group_id||row.thread_id||row.id);groups.set(g,[...(groups.get(g)||[]),row.id]);}
  if(groups.size<3)throw new Error('at least three independent groups are required');
  const hash=(g:string)=>createHash('sha256').update(`${seed}:${g}`).digest('hex');
  const order=[...groups.keys()].sort((a,b)=>hash(a).localeCompare(hash(b)));
  const total=fractions.reduce((a,b)=>a+b,0), targets=fractions.map(f=>groups.size*f/total), counts=[0,0,0];
  const out:Record<string,string[]>={development:[],validation:[],test:[]};
  order.forEach((g,index)=>{let slot=index;if(index>=3){slot=0;for(let i=1;i<3;i++)if(targets[i]!-counts[i]!>targets[slot]!-counts[slot]!)slot=i;}counts[slot]!++;out[names[slot]!]!.push(...groups.get(g)!);});
  for(const ids of Object.values(out))ids.sort();return out;
}
