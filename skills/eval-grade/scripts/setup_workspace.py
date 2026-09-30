"""Install this skill's available templates without overwriting customized project files."""
from pathlib import Path
import argparse,json,re

def install(skill,root,language):
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    copied=[];preserved=[]
    templates=skill/'templates'
    for src in sorted(templates.rglob('*')) if templates.exists() else []:
        if not src.is_file() or src.suffix not in {'.py','.ts','.mjs','.html','.css','.js'}:continue
        rel=src.relative_to(templates)
        if 'review-app' in rel.parts:
            if src.name=='server.py' and language=='typescript' or src.name=='server.mjs' and language=='python':continue
            dst=root/'review-app'/src.name
        else:
            if language=='python' and (src.suffix in {'.ts','.mjs'} or 'typescript' in rel.parts):continue
            if language=='typescript' and ('python' in rel.parts or src.suffix=='.py' and src.name not in {'split_cases.py','grouped_split.py','sample_traces.py','export_bundle.py'}):continue
            dst=root/'scripts'/src.name
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():preserved.append(str(dst));continue
        dst.write_text(src.read_text().replace('.eval/default',root.as_posix()));copied.append(str(dst))
    state=root/'workflow.json'
    current=json.loads(state.read_text()) if state.exists() else {'schema_version':1,'flow':root.name,'track':None,'stage':'inspect','milestones':{},'decisions':{}}
    current['root']=str(root);current.setdefault('installed_skills',{})[skill.name]=language
    state.write_text(json.dumps(current,indent=2)+'\n')
    return {'copied':copied,'preserved':preserved,'root':str(root)}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--flow',default='default');p.add_argument('--root');p.add_argument('--language',choices=['python','typescript'],default='python');p.add_argument('--skill',type=Path)
    a=p.parse_args()
    if not re.fullmatch('[a-zA-Z0-9_-]+',a.flow):p.error('flow must be a simple name')
    skill=a.skill or Path(__file__).resolve().parents[1]
    print(json.dumps(install(skill,Path(a.root or '.eval/'+a.flow),a.language),indent=2))
