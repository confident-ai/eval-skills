"""Export native toolkit records to portable evidence contract v1; never overwrite a bundle."""
import argparse,hashlib,json,shutil
from pathlib import Path

def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
def write_lines(path,rows):
    path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
def export(root,variant,out):
    if out.exists():raise ValueError('output already exists; choose a new bundle directory')
    cases=read_lines(root/'dataset/goldens.jsonl'); run=root/'runs'/variant
    results=read_lines(run/'results.jsonl'); errors=read_lines(run/'errors.jsonl')
    if not cases:raise ValueError('no cases to export')
    summary=json.loads((run/'summary.json').read_text()) if (run/'summary.json').exists() else {}
    portable=[]; case_ids={c['id'] for c in cases}
    if len(case_ids)!=len(cases):raise ValueError('duplicate case IDs')
    for c in cases:
        portable.append({**c,'group_id':c.get('group_id',c['id']),'input':c.get('input',c.get('scenario','')),'source':c.get('source',{'kind':'imported'})})
    out.mkdir(parents=True);(out/'traces').mkdir()
    write_lines(out/'cases.jsonl',portable)
    converted=[]; used=set()
    for row in results:
        key=(row['case_id'],row['rep'])
        if key in used or row['case_id'] not in case_ids:raise ValueError('duplicate or unknown result')
        used.add(key)
        name=hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24]+'.json'
        # Preserve captured runtime trace when supplied. Otherwise this is explicitly a runner record.
        trace=row.get('trace') or {'format':'runner-record','record':row,'limitation':'No full runtime trace returned by application adapter'}
        (out/'traces'/name).write_text(json.dumps(trace,ensure_ascii=False,indent=2))
        grades={k:{'score':float(g.get('score',int(g['passed']))),'reason':g.get('reason',''),'grader_version':g.get('grader_version',row.get('harness_hash','imported'))} for k,g in row['grades'].items()}
        if not grades:continue  # collection-only output is preserved as a trace, not a fabricated graded result
        converted.append({'case_id':row['case_id'],'rep':row['rep'],'status':'ok','output':row['output'],'grades':grades,'trace_ref':'traces/'+name,'usage':row.get('usage'),'latency_s':row.get('latency_s')})
    for key in sorted({(e['case_id'],e['rep']) for e in errors}-used):
        if key[0] not in case_ids:raise ValueError('unknown error case')
        attempts=[e for e in errors if (e['case_id'],e['rep'])==key]; last=attempts[-1]
        name=hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24]+'.json'
        (out/'traces'/name).write_text(json.dumps({'format':'runner-errors','attempts':attempts},indent=2))
        status='timeout' if last['failure_class']=='timeout' else 'grader_error' if last['stage']=='grader' else 'app_error'
        converted.append({'case_id':key[0],'rep':key[1],'status':status,'output':None,'grades':{},'trace_ref':'traces/'+name})
    write_lines(out/'results.jsonl',converted)
    write_lines(out/'attempts.jsonl',read_lines(run/'attempts.jsonl'))
    trace_to_case={c.get('trace_id',c.get('source',{}).get('trace_id',c['id'])):c['id'] for c in cases}
    notes=[]; annotations=root/'review-app/annotations.json'
    if annotations.exists():
        for trace_id,a in json.loads(annotations.read_text()).items():
            case_id=a.get('case_id') if a.get('case_id') in case_ids else trace_to_case.get(trace_id)
            if not case_id:continue
            base={'case_id':case_id,'origin':a.get('origin','human'),'note':a.get('note',''),'reviewed_by':a.get('reviewed_by'),'metadata':{'source_trace_id':trace_id}}
            labels=a.get('labels') or {'discovery':a.get('verdict')}
            for criterion,label in labels.items():
                n={**base,'id':a.get('id','note:'+trace_id)+':'+criterion,'criterion_id':criterion,'status':'uncertain' if label in {'uncertain','defer'} else 'confirmed' if a.get('reviewed_by') else 'suggested'}
                if label in {'pass','fail'}:n['label']=label
                notes.append(n)
    write_lines(out/'annotations.jsonl',notes)
    # Preserve the native review export too: taxonomy references native annotation IDs.
    if (root/'review-app').exists():
        native=out/'review';native.mkdir()
        for name in ['annotations.json','taxonomy.json','failure_modes.json']:
            src=root/'review-app'/name
            if src.exists():shutil.copyfile(src,native/name)
        normalized=root/'traces/traces.jsonl'
        if normalized.exists():shutil.copyfile(normalized,native/'traces.jsonl')
    digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
    manifest={'schema_version':1,'flow':root.name,'dataset_version':digest(portable),'run_id':variant,'run_fingerprint':digest({'dataset':portable,'harnesses':sorted({r.get('harness_hash','unknown') for r in results})}),'expected_results':summary.get('cases',len(cases))*summary.get('reps',1),'metadata':{'native_summary':summary,'usage_accounting':'attempts are call records; do not add terminal-row usage again'}}
    splits={}
    for name in ['development','validation','test']:
        path=root/'runs'/(name+'_ids.json')
        if path.exists():splits[name]=json.loads(path.read_text())
    if splits:manifest['splits']=splits
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.eval/default');p.add_argument('--variant',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(export(Path(a.root),a.variant,Path(a.output)))
