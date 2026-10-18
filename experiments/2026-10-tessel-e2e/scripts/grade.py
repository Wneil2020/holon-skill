import os,re,glob
N='announcement-banner'
def R(p):
    try: return open(p,encoding='utf-8').read()
    except Exception: return None
def grade(repo):
    pd=f'{repo}/src/parts/{N}'; idx=R(f'{pd}/index.tsx'); code=idx or ''
    allcode="\n".join(R(p) or '' for p in glob.glob(f'{repo}/src/**/*.tsx',recursive=True)+glob.glob(f'{repo}/src/**/*.ts',recursive=True)+glob.glob(f'{repo}/src/**/*.css',recursive=True))
    partcode="\n".join(R(p) or '' for p in glob.glob(f'{pd}/**/*',recursive=True) if not p.endswith('.spec.tsx') and os.path.isfile(p))
    c={}
    c['F1_location']= idx is not None and not glob.glob(f'{repo}/src/components/**',recursive=True)
    c['F2_wrapper']= bool(re.search(r'export\s+default\s+tessel\.part\(\s*["\']%s["\']'%N,code)) and '@tessel/core' in code
    c['F3_tokens']= 'var(--ts-color-' in partcode and not re.search(r'#[0-9a-fA-F]{3,8}\b|rgba?\(|\b(color|background(-color)?)\s*:\s*["\']?(white|black|red|blue|yellow|gray|grey)\b',partcode)
    c['F4_layer']= 'var(--ts-layer-banner)' in partcode and not re.search(r'z-?index["\']?\s*:\s*["\']?\d',partcode,re.I)
    c['F5_strings']= bool(re.search(r'tessel\.useStrings\(\s*["\']%s["\']'%N,code)) and bool(re.search(r'\bt\(\s*["\']',code))
    en=R(f'{repo}/locales/en/{N}.strings'); zh=R(f'{repo}/locales/zh-Hans/{N}.strings')
    def ok(s): 
        if not s: return False
        ls=[l for l in s.splitlines() if l.strip() and not l.strip().startswith('#')]
        return bool(ls) and all(re.match(r'^[A-Za-z0-9_.-]+\s*=\s*".*"\s*$',l) for l in ls) and not any(l.strip().startswith(N+'.') for l in ls)
    c['F6_string_files']= ok(en) and ok(zh) and not glob.glob(f'{repo}/locales/zh/*') and not glob.glob(f'{repo}/locales/zh-CN/*')
    c['F7_dismiss']= 'data-ts-dismiss' in code and bool(re.search(r'aria-label=\{\s*t\(',code))
    # the key may be inlined or held in a constant defined in the part's code
    consts=dict(re.findall(r'(?:const|let)\s+([A-Za-z_$][\w$]*)\s*(?::\s*\w+\s*)?=\s*["\']([^"\']+)["\']',code))
    keys=re.findall(r'tessel\.store\.session(?:<[^>]*>)?\(\s*(?:["\'`]([^"\'`]+)["\'`]|([A-Za-z_$][\w$]*))',code)
    keys=[a or consts.get(b,'') for a,b in keys]
    c['F8_store']= any(k.startswith(N+'.') for k in keys) and not re.search(r'localStorage|sessionStorage',re.sub(r'//[^\n]*|/\*.*?\*/','',allcode,flags=re.S))
    spec=R(f'{pd}/{N}.spec.tsx')
    c['F9_test']= bool(spec) and bool(re.search(r'renderPart',spec)) and '@tessel/testkit' in spec and 'it(' in spec
    ch=R(f'{repo}/changes/next/{N}.md'); cl=R(f'{repo}/CHANGELOG.md')
    c['F10_change_note']= bool(ch) and ch.strip().splitlines()[0].strip() in ('kind: feature','kind: fix') and cl==R(os.path.join(os.path.dirname(os.path.abspath(__file__)),'scaffold','CHANGELOG.md'))
    return c
