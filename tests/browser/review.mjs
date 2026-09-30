// Install Playwright separately; point PLAYWRIGHT_MODULE at its index.mjs.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../skills/eval-discover/templates/review-app', import.meta.url));
const browser=await chromium.launch({...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}),headless:true});
async function start(language,dir,port,mode='review'){
 const cmd=language==='python'?(process.env.PYTHON || 'python3'):'node';
 const child=spawn(cmd,[root+(language==='python'?'/server.py':'/server.mjs'),'--port',String(port),'--dir',dir+'/review','--traces',dir+'/traces.jsonl','--mode',mode]);
 await new Promise((resolve,reject)=>{child.stdout.once('data',resolve);child.once('error',reject);child.once('exit',c=>reject(new Error('server exited '+c)));});return child;
}
try {
 for(const [idx,language] of ['python','node'].entries()){
  const dir=mkdtempSync(join(tmpdir(),'eval-browser-'+language+'-'));mkdirSync(dir+'/review');
  writeFileSync(dir+'/traces.jsonl',JSON.stringify({trace_id:'t0',case_id:'c0',input:'<script>window.__pwn=1</script>',output:'Wrong 45-day return window',metadata:{judge_hint:'MODEL-PREDICTION-MUST-BE-HIDDEN'},steps:[]})+'\n');
  const port=18870+idx;let server=await start(language,dir,port);
  const context=await browser.newContext({viewport:{width:1280,height:900}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try {
   await page.goto('http://127.0.0.1:'+port);await page.locator('#reviewer').fill('Browser fixture reviewer');await page.locator('#note').fill('Policy says 30 days, output says 45.');await page.locator('#save-status').filter({hasText:'Saved'}).waitFor();
   await page.reload();await page.locator('#note').filter({visible:true}).waitFor();assert.equal(await page.locator('#note').inputValue(),'Policy says 30 days, output says 45.');assert.equal(await page.evaluate(()=>window.__pwn),undefined);
   const stale=await context.newPage();await stale.goto('http://127.0.0.1:'+port);await stale.locator('#note').waitFor();
   await page.locator('#note').fill('Newer review note');await page.locator('#save-status').filter({hasText:'Saved'}).waitFor();
   await stale.locator('#note').fill('Older edit');await stale.locator('#save-status').filter({hasText:'Stale annotation'}).waitFor();await stale.close();
   await page.getByRole('button',{name:'Progress',exact:true}).click();
   async function prompts(button,answers){const handler=async dialog=>{await dialog.accept(answers.shift());};page.on('dialog',handler);await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/taxonomy')&&r.status()===200),page.getByRole('button',{name:button,exact:true}).click()]);page.off('dialog',handler);}
   await prompts('Add mode',['window','Wrong return window']);await prompts('Add mode',['policy','Contradicts policy']);
   await page.getByRole('combobox',{name:'Mode for t0'}).selectOption('window');await page.getByRole('button',{name:'Suggest assignment t0',exact:true}).click();await page.getByText('window — suggested',{exact:false}).waitFor();
   await page.getByRole('button',{name:'Confirm definition window',exact:true}).click();
   let data=await(await context.request.get('http://127.0.0.1:'+port+'/api/export')).json();assert.equal(data.taxonomy.assignments[0].status,'suggested');
   await prompts('Rename window',['Return window mismatch']);await prompts('Merge modes',['window,policy','merged','Policy contradiction']);
   await prompts('Split mode',['merged','window-only','Wrong duration','fee-only','Wrong fee']);
   await page.getByText('Unresolved — uncertain',{exact:false}).waitFor();await page.getByRole('combobox',{name:'Mode for t0'}).selectOption('window-only');await page.getByRole('button',{name:/^Reassign /}).click();await page.getByText('window-only — suggested',{exact:false}).waitFor();await page.getByRole('button',{name:/^Confirm assignment /}).click();
   data=await(await context.request.get('http://127.0.0.1:'+port+'/api/export')).json();assert.equal(data.taxonomy.assignments[0].status,'confirmed');assert(data.taxonomy.history.length>=8);
   await page.getByRole('button',{name:'Open trace t0',exact:true}).click();assert.equal(await page.locator('#note').inputValue(),'Newer review note');
   await page.screenshot({path:join(dir,'review.png'),fullPage:true});
   server.kill();await new Promise(resolve=>server.once('exit',resolve));server=await start(language,dir,port,'label');await page.reload();
   await page.getByRole('button',{name:'Uncertain',exact:true}).first().click();await page.locator('#save-status').filter({hasText:'Saved'}).waitFor();assert(!await page.locator('#trace-body').innerText().then(t=>t.includes('MODEL-PREDICTION-MUST-BE-HIDDEN')));
   await page.reload();data=await(await context.request.get('http://127.0.0.1:'+port+'/api/export')).json();assert(Object.values(data.annotations.t0.labels).includes('uncertain'));assert.deepEqual(errors,[]);
   console.log(language+': notes/reload/conflict/merge/split/reassign/export/uncertain/blind-label/XSS passed');
  }finally{server.kill();await context.close();}
 }
}finally{await browser.close();}
