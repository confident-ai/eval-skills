"""Behavioral invariants introduced by the integration, independent of wording."""
import importlib.util,json,sys
from pathlib import Path
import pytest
from conftest import template,run_py,write_jsonl,read_jsonl

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_group_disjoint_and_stable():
    m=module(template('eval-grade','grouped_split.py'),'split_test')
    records=[{'id':f'{g}-{i}','group_id':str(g)} for g in range(12) for i in range(3)]
    a=m.grouped_split(records);b=m.grouped_split(list(reversed(records)))
    assert a==b and all(a.values())
    group_sets=[{x.split('-')[0] for x in ids} for ids in a.values()]
    assert not any(x&y for i,x in enumerate(group_sets) for y in group_sets[i+1:])
    with pytest.raises(ValueError):m.grouped_split(records[:3])

def test_review_conflict_taxonomy_history_and_uncertain(project):
    m=module(template('eval-discover','review-app','server.py'),'review_test')
    traces=project/'traces.jsonl';write_jsonl(traces,[{'trace_id':'t','case_id':'c','input':'hello','output':'wrong'}])
    store=m.ReviewStore(traces,project/'review','review')
    a=store.annotate({'trace_id':'t','revision':0,'reviewed_by':'fixture-human','note':'wrong amount','verdict':'uncertain','labels':{'amount':'uncertain'}})
    assert a['revision']==1 and a['labels']['amount']=='uncertain'
    with pytest.raises(m.Conflict):store.annotate({'trace_id':'t','revision':0,'reviewed_by':'fixture-human'})
    with pytest.raises(ValueError):store.annotate({'trace_id':'missing','revision':0,'reviewed_by':'fixture-human'})
    assignment={'id':'a','annotation_id':a['id'],'trace_id':'t','case_id':'c','mode_id':'amount','origin':'agent','status':'suggested'}
    t=store.save_taxonomy({'revision':0,'reviewed_by':'fixture-human','modes':[{'id':'amount','definition':'Wrong amount','status':'confirmed'}],'assignments':[assignment]})
    assert t['assignments'][0]['status']=='suggested' and t['modes'][0]['reviewed_by']=='fixture-human'
    with pytest.raises(m.Conflict):store.save_taxonomy({'revision':0})
    t['assignments'][0]['status']='confirmed';t['reviewed_by']='fixture-human'
    revised=store.save_taxonomy(t)
    assert revised['assignments'][0]['reviewed_by']=='fixture-human' and len(revised['history'])==2
    assert store.data()['taxonomy']['revision']==2

def test_app_projection_ledger_and_portable_export(project):
    root=project/'.eval/default'
    write_jsonl(root/'dataset/goldens.jsonl',[{'id':'c','group_id':'g','input':'q','expected':'SECRET','source':{'kind':'synthetic'}}])
    scripts=root/'scripts';scripts.mkdir()
    (scripts/'app_adapter.py').write_text('def run_case(case):\n assert "expected" not in case and "source" not in case\n return {"output":"answer","usage":{"input_tokens":3}}\n')
    graders=root/'graders';graders.mkdir();(graders/'graders.py').write_text('def grade(case,result):\n assert case["expected"]=="SECRET"\n return {"passed":True,"reason":"ok","usage":{"output_tokens":2}}\nGRADERS={"check":grade}\n')
    run_py(template('eval-run','run_evals.py'),'--variant','baseline',cwd=project)
    summary=json.loads((root/'runs/baseline/summary.json').read_text())
    assert summary['usage_totals']=={'input_tokens':3,'output_tokens':None} and not summary['usage_complete']
    ledger=read_jsonl(root/'runs/baseline/attempts.jsonl');assert [a['stage'] for a in ledger]==['app','judge']
    assert summary['usage_by_stage']['judge']['measured_tokens']['output_tokens']==2
    output=project/'export'
    run_py(template('eval-run','export_bundle.py'),'--variant','baseline','--output',str(output),cwd=project)
    validator=template('eval-run').parent/'scripts/artifacts.py'
    run_py(validator,'validate',str(output),cwd=project)
    result=read_jsonl(output/'results.jsonl')[0]
    assert result['grades']['check']['score']==1
    assert run_py(template('eval-run','export_bundle.py'),'--variant','baseline','--output',str(output),cwd=project,check=False).returncode!=0

def test_setup_preserves_customization_and_root(project):
    skill=template('eval-discover').parent
    setup=skill/'scripts/setup_workspace.py';target=project/'custom-root'
    run_py(setup,'--root',str(target),cwd=project)
    server=target/'review-app/server.py';assert str(target) in server.read_text()
    server.write_text('# custom\n')
    run_py(setup,'--root',str(target),cwd=project)
    assert server.read_text()=='# custom\n'
    assert json.loads((target/'workflow.json').read_text())['installed_skills']['eval-discover']=='python'
