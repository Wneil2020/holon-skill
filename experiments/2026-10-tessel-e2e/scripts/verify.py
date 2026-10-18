"""Run the agent's work for real: its own spec, a hidden behavioral spec (jsdom), and a real page in Chromium with screenshots."""
import os,sys,json,shutil,subprocess,re
sys.path.insert(0,os.environ.get('PLAYWRIGHT_PY','/workspace/tools/py'))
HERE=os.path.dirname(os.path.abspath(__file__)); RT=f'{HERE}/runtime'; SH=f'{RT}/shim'; N='announcement-banner'
def sh(cmd,cwd,timeout=180,env=None):
    try:
        r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout,env={**os.environ,**(env or {})})
        return r.returncode,(r.stdout+r.stderr)
    except subprocess.TimeoutExpired: return -9,'timeout'
def entry(w):
    """The part's entry: the conventional one, else whatever file the agent made for the banner."""
    import glob
    c=[f'{w}/src/parts/{N}/index.tsx',f'{w}/src/parts/{N}/index.ts',f'{w}/src/parts/{N}/index.jsx']
    c+=sorted(glob.glob(f'{w}/src/**/*[Aa]nnouncement*[Bb]anner*.tsx',recursive=True))+sorted(glob.glob(f'{w}/src/**/announcement-banner/index.*',recursive=True))
    c=[x for x in c if os.path.exists(x) and not re.search(r'\.(spec|test)\.',x)]
    return c[0] if c else None
def defaults(w):
    """Prop defaults declared in part.manifest.json (the platform resolves these before render)."""
    try: m=json.load(open(f'{w}/src/parts/{N}/part.manifest.json'))
    except Exception: return {}
    out={}; p=m.get('props',m) if isinstance(m,dict) else {}
    if isinstance(p,dict):
        for k,v in p.items():
            if isinstance(v,dict) and 'default' in v: out[k]=v['default']
    elif isinstance(p,list):
        for v in p:
            if isinstance(v,dict) and 'name' in v and 'default' in v: out[v['name']]=v['default']
    if isinstance(m,dict) and isinstance(m.get('defaults'),dict): out.update(m['defaults'])
    return out
def vitest(w,files):
    SH=f"{w}/.shim"; shutil.rmtree(SH,ignore_errors=True); shutil.copytree(f"{HERE}/runtime/shim",SH)
    files=[f.replace(f"{HERE}/runtime/shim",SH) for f in files]
    json.dump(defaults(w),open(f"{SH}/defaults.json","w"))
    cfg=f'''import {{ defineConfig }} from "vitest/config";
export default defineConfig({{ resolve: {{ alias: {{
 "@tessel/core": "{SH}/core.jsx", "@tessel/testkit": "{SH}/testkit.jsx", "@part": "{entry(w)}" }} }},
 test: {{ environment: "jsdom", globals: true, setupFiles: ["{SH}/setup.mjs"], include: {json.dumps(files)}, testTimeout: 15000 }} }});'''
    open(f'{w}/vitest.config.mjs','w').write(cfg)
    code,out=sh([f'{RT}/node_modules/.bin/vitest','run','--config',f'{w}/vitest.config.mjs','--reporter=json','--outputFile',f'{w}/vt.json'],w,env={'TESSEL_REPO':w})
    try: j=json.load(open(f'{w}/vt.json')); return j['numPassedTests'],j['numTotalTests'],out[-1500:]
    except Exception: return 0,0,out[-1500:]
PAGE='''import React from "react"; import { createRoot } from "react-dom/client";
import Part from "@part"; import "./tokens.css";
globalThis.__TESSEL_STRINGS__ = STRINGS;
const lang = new URLSearchParams(location.search).get("lang") || "en"; globalThis.__TESSEL_LANG__ = lang; document.documentElement.lang = lang;
function App(){ return (<div><Part {...DEFAULTS} lang={lang} locale={lang} />
 <header style={{background:"#14233c",color:"#fff",padding:"14px 24px",fontWeight:600}}>Tessel · Orders</header>
 <main style={{padding:24}}><h1 style={{fontSize:22,margin:"0 0 12px"}}>{lang==="en"?"Orders":"订单"}</h1>
 {[1,2,3].map(i=><div key={i} style={{background:"#fff",border:"1px solid #e3e6ea",borderRadius:8,padding:16,marginBottom:10}}>#{1040+i} · {lang==="en"?"Shipped":"已发货"}</div>)}</main></div>); }
createRoot(document.getElementById("root")).render(<App />);'''
def page(w,out):
    sys.path.insert(0,HERE)
    strings=json.loads(subprocess.run(['node','-e',f'import("{SH}/strings.mjs").then(m=>console.log(JSON.stringify(m.loadStrings("{w}"))))'],capture_output=True,text=True).stdout or '{}')
    shutil.copy(f'{SH}/tokens.css',w); open(f'{w}/page.jsx','w').write(PAGE)
    os.makedirs(out,exist_ok=True)
    code,log=sh([f'{RT}/node_modules/.bin/esbuild',f'{w}/page.jsx','--bundle','--jsx=automatic',f'--outdir={out}','--loader:.js=jsx',
                 f'--alias:@tessel/core={SH}/core.jsx',f'--alias:@part={entry(w)}',f'--define:STRINGS={json.dumps(strings)}',f'--define:DEFAULTS={json.dumps(defaults(w))}','--define:process.env.NODE_ENV="production"'],w,timeout=60)
    if code: return {'build':False,'log':log[-1200:]}
    open(f'{out}/index.html','w').write('<!doctype html><meta charset="utf-8"><title>Tessel</title><link rel="stylesheet" href="page.css"><div id="root"></div><script src="page.js"></script>')
    from playwright.sync_api import sync_playwright
    res={'build':True,'errors':[]}
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM','/usr/bin/chromium'),args=['--no-sandbox','--allow-file-access-from-files'])
        ctx=b.new_context(viewport={'width':1000,'height':420})
        pg=ctx.new_page(); pg.on('pageerror',lambda e:res['errors'].append(str(e)[:300]))
        url='file://'+out+'/index.html'
        # file:// has no per-origin sessionStorage guarantees across reloads in all builds; serve over http instead
        srv=subprocess.Popen([sys.executable,'-u','-m','http.server','0','--bind','127.0.0.1'],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        port=None
        for _ in range(50):
            l=srv.stdout.readline(); m=re.search(r'port (\d+)',l)
            if m: port=m.group(1); break
        url=f'http://127.0.0.1:{port}/index.html'
        try:
            for lang in ['en','zh-Hans']:
                pg.goto(f'{url}?lang={lang}'); pg.wait_for_timeout(400); pg.screenshot(path=f'{out}/{lang}.png')
                res[f'text_{lang}']=pg.inner_text('#root')[:300]
            pg.goto(f'{url}?lang=en'); pg.wait_for_timeout(300)
            d=pg.query_selector('[data-ts-dismiss]') or pg.query_selector('button')
            res['dismiss_found']=bool(d)
            if d:
                d.click(); pg.wait_for_timeout(300); pg.screenshot(path=f'{out}/en-dismissed.png')
                after=pg.inner_text('#root'); pg.reload(); pg.wait_for_timeout(400)
                res['hidden_after_click']= res['text_en']!=after
                res['hidden_after_reload']= pg.inner_text('#root')==after
                p2=b.new_context().new_page(); p2.goto(f'{url}?lang=en'); p2.wait_for_timeout(400)
                res['back_in_new_session']= p2.inner_text('#root')==res['text_en']
        finally: srv.kill(); b.close()
    return res
def verify(repo,out):
    w=f'{RT}/work/{os.path.basename(os.path.dirname(repo))}-{os.getpid()}'; shutil.rmtree(w,ignore_errors=True); shutil.copytree(repo,w)
    r={}
    try:
        if not entry(w): return {'exists':False}
        r['entry']=os.path.relpath(entry(w),w)
        import glob
        specs=sorted(set(glob.glob(f'{w}/src/**/*.spec.tsx',recursive=True)+glob.glob(f'{w}/src/**/*.test.tsx',recursive=True)+glob.glob(f'{w}/src/**/*.test.ts',recursive=True)+glob.glob(f'{w}/src/**/*.spec.ts',recursive=True)))
        if specs: r['own_tests']=vitest(w,specs)[:2]
        p,t,log=vitest(w,[f'{SH}/behavior.spec.jsx']); r['behavior']=[p,t]; r['behavior_log']=log if p<t else ''
        try: r['page']=page(w,out)
        except Exception as e: r['page']={'error':str(e)[:300]}
    finally: shutil.rmtree(w,ignore_errors=True)
    return r
if __name__=='__main__':
    print(json.dumps(verify(sys.argv[1],sys.argv[2]),ensure_ascii=False,indent=1))
