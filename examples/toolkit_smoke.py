"""Credential-free integration journey with synthetic review decisions, never real sign-off."""
from pathlib import Path
import argparse,importlib.util,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    project=Path(a.output).resolve()
    if project.exists():raise SystemExit('Choose a new output directory')
    project.mkdir(parents=True);root=project/'.eval/default'
    setup=load(ROOT/'scripts/setup_workspace.py','setup')
    for skill in ['eval-trace','eval-discover','eval-error-analysis','eval-grade','eval-run','eval-descent','eval-maintain']:
        setup.install(ROOT/'skills'/skill,root,'python')
    shutil.copytree(ROOT/'examples/support-bot',project/'app')
    env={**os.environ,'EVAL_SKILLS_TRACE_MODE':'local','EVAL_SKILLS_TRACES_DIR':str(root/'traces'),'SUPPORT_BOT_OFFLINE':'1','DEEPEVAL_TELEMETRY_OPT_OUT':'1','PYTHONDONTWRITEBYTECODE':'1'}
    env.pop('CONFIDENT_API_KEY',None);env.pop('OPENAI_API_KEY',None)
    def run(script,*args):
        subprocess.run([sys.executable,str(script),*map(str,args)],cwd=project,env=env,check=True)
    for question in ['Can I return shoes?','Where is order A17?','What is shipping time?']:
        run(project/'app/app.py',question)
    run(root/'scripts/normalize_traces.py')
    traces=[json.loads(l) for l in (root/'traces/traces.jsonl').read_text().splitlines()]
    assert len(traces)==3 and all(t.get('steps') for t in traces)
    run(root/'scripts/sample_traces.py','--n','3')
    review=load(root/'review-app/server.py','review');store=review.ReviewStore(root/'traces/traces.jsonl',root/'review-app','review')
    # Synthetic fixture actors exercise persistence, not human calibration.
    for t in traces:
        store.annotate({'trace_id':t['trace_id'],'revision':0,'reviewed_by':'SYNTHETIC-TEST-FIXTURE','verdict':'fail' if '45 days' in str(t['output']) else 'uncertain','note':'Synthetic fixture: inspect return window','labels':{}})
    bad=next(t for t in traces if '45 days' in str(t['output']))
    note=store.data()['annotations'][bad['trace_id']]
    store.save_taxonomy({'revision':0,'reviewed_by':'SYNTHETIC-TEST-FIXTURE','modes':[{'id':'return-window','definition':'States an unsupported return window','status':'proposed'}],'assignments':[{'id':'fixture-assignment','annotation_id':note['id'],'case_id':note['case_id'],'trace_id':bad['trace_id'],'mode_id':'return-window','origin':'agent','status':'suggested'}]})
    cases=[{'id':t['trace_id'],'group_id':t['thread_id'] or t['trace_id'],'trace_id':t['trace_id'],'input':t['input'],'expected':'30 days','source':{'kind':'synthetic'}} for t in traces]
    (root/'dataset').mkdir();(root/'dataset/goldens.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in cases))
    (root/'graders').mkdir();(root/'graders/graders.py').write_text('def grade(c,r):\n return {"passed":"45 days" not in r["output"],"reason":"Checks only the known window regression"}\nGRADERS={"return-window":grade}\n')
    (root/'scripts/app_adapter.py').write_text('import sys,atexit\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()/"app"))\nimport app,confident_trace as ct\napp.setup_tracing("smoke")\natexit.register(ct.shutdown)\ndef run_case(c):\n return {"output":app.answer(c["input"])}\n')
    run(root/'scripts/split_cases.py')
    run(root/'scripts/run_evals.py','--variant','baseline','--app-version','smoke-baseline')
    app=project/'app/app.py';app.write_text(app.read_text().replace('return items within 45 days','return items within 30 days'))
    run(root/'scripts/run_evals.py','--variant','candidate','--app-version','smoke-candidate','--compare','baseline')
    run(root/'scripts/report.py')
    run(root/'scripts/export_bundle.py','--variant','candidate','--output',project/'bundle')
    run(ROOT/'skills/eval-run/scripts/artifacts.py','validate',project/'bundle')
    summary=json.loads((root/'runs/candidate/summary.json').read_text())
    assert summary['pass_rate_all']==1 and summary['compare']['delta']>0
    print('Synthetic integration journey complete:',project)
    print('No paid model calls or real human calibration performed.')
if __name__=='__main__':main()
