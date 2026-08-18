from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import parse_qs,unquote,urljoin,urlparse
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'content/3as/subjects/french/variants/common_or_scientific'
PDF_ROOT=OUT/'resources'; MANIFEST=OUT/'source_metadata/french_scientific_sources.json'
SEEDS=[
 {'site':'dzexams','suffix':'dzexams','url':'https://www.dzexams.com/ar/3as/francais/as_d1','default_term':'first_term','root':'dzexams.com'},
 {'site':'eddirasa','suffix':'eddirasa','url':'https://eddirasa.com/ens-sec/3as/francais/tests-science-term-1/','default_term':'first_term','root':'eddirasa.com'},
 {'site':'ency_education','suffix':'ency_education','url':'https://3as.ency-education.com/french-sci-exams.html','default_term':None,'root':'ency-education.com'}]
HEAD={'User-Agent':'Mozilla/5.0 (MY Algeria BAC content importer)'}
TERM=[('first_term',re.compile(r'premier|1er|term[ei]?[- ]?1|الفصل\s*(?:الأول|1)',re.I)),('second_term',re.compile(r'deuxi|2[eè]me|term[ei]?[- ]?2|الفصل\s*(?:الثاني|2)',re.I)),('third_term',re.compile(r'troisi|3[eè]me|term[ei]?[- ]?3|الفصل\s*(?:الثالث|3)',re.I))]
YEAR=re.compile(r'(?:19|20)\d{2}(?:[/-](?:19|20)?\d{2})?'); PDF=re.compile(r'\.pdf(?:$|[?#])',re.I); CORR=re.compile(r'corrig|correction|solution|حل|تصحيح',re.I)
s=requests.Session(); s.headers.update(HEAD)
def clean(x):
 x=re.sub(r'\s+',' ',x.strip()); x=re.sub(r'[\\/:*?"<>|]+','-',x); return re.sub(r'-+','-',x).strip(' .-')[:180] or 'document'
def root(url,seed):
 h=urlparse(url).netloc.lower().split(':')[0]; return h==seed['root'] or h.endswith('.'+seed['root'])
def term(text,default):
 for name,p in TERM:
  if p.search(text): return name
 return default or 'unspecified'
def embedded(url):
 p=urlparse(url)
 if PDF.search(p.path): return url
 for k in ('file','pdf','url','src','document'):
  for v in parse_qs(p.query).get(k,[]):
   v=unquote(v)
   if PDF.search(urlparse(v).path): return v
 return None
def fetch_html(url):
 r=s.get(url,timeout=45,allow_redirects=True); r.raise_for_status();
 if 'pdf' in (r.headers.get('content-type') or '').lower(): raise ValueError('pdf response')
 return r.text,r.url
def links(seed):
 seen=set(); out={}; q=[(seed['url'],0,seed['default_term'])]
 while q:
  page,d,inherited=q.pop(0)
  if page in seen or d>2: continue
  seen.add(page)
  try: html,final=fetch_html(page)
  except Exception as e: print('WARN',page,e); continue
  soup=BeautifulSoup(html,'html.parser'); current=inherited
  for el in soup.find_all(['h1','h2','h3','h4','h5','h6','a','iframe','embed','object','source']):
   if el.name.startswith('h'):
    t=term(el.get_text(' ',strip=True),None)
    if t!='unspecified': current=t
    continue
   raw=[]
   for a in ('href','src','data','data-href','data-url','data-pdf','onclick'):
    if el.get(a): raw.append(str(el.get(a)))
   if not raw: continue
   anchor=el.get_text(' ',strip=True); ctx=' '.join([anchor,el.parent.get_text(' ',strip=True) if el.parent else anchor])
   for r0 in raw:
    u=urljoin(final,r0)
    e=embedded(u)
    if e: out[e]=(anchor,ctx,final,current); continue
    if d<2 and root(u,seed) and re.search(r'exemple|devoir|test|exam|composition|corrig|sujet',anchor+' '+u,re.I): q.append((u,d+1,current))
  for m in re.findall(r'https?://[^\"\'<>\s]+\.pdf(?:\?[^\"\'<>\s]*)?',html,re.I): out[m]=('', '', final,current)
 return [(u,*v) for u,v in out.items()]
def fname(url,anchor,suffix,used):
 stem=clean(unquote(Path(urlparse(url).path).stem) or anchor or 'document'); base=f'{stem}__{suffix}'; c=base+'.pdf'
 if c in used: c=f'{base}__{hashlib.sha256(url.encode()).hexdigest()[:8]}.pdf'
 used.add(c); return c
def folder(t,c): return PDF_ROOT/'corrections'/t if c else PDF_ROOT/{'first_term':'first_term','second_term':'second_term','third_term':'third_term','unspecified':'unspecified'}.get(t,'unspecified')
def main():
 records=[]; seen_hash={}; used=set(); PDF_ROOT.mkdir(parents=True,exist_ok=True); MANIFEST.parent.mkdir(parents=True,exist_ok=True)
 for seed in SEEDS:
  ls=links(seed); print(seed['site'],len(ls))
  for pdf,anchor,ctx,page,section in ls:
   t=section or term(' '.join([anchor,ctx,page,pdf]),seed['default_term']); corr=bool(CORR.search(' '.join([anchor,ctx,pdf]))); dst=folder(t,corr); dst.mkdir(parents=True,exist_ok=True); path=dst/fname(pdf,anchor,seed['suffix'],used)
   try:
    r=s.get(pdf,timeout=90,stream=True,allow_redirects=True); r.raise_for_status(); ct=(r.headers.get('content-type') or '').lower()
    if 'pdf' not in ct and not PDF.search(urlparse(r.url).path): raise ValueError(f'not pdf: {ct} {r.url}')
    h=hashlib.sha256()
    with path.open('wb') as f:
     for ch in r.iter_content(1024*1024):
      if ch: h.update(ch); f.write(ch)
    digest=h.hexdigest(); dup=seen_hash.get(digest); status='duplicate_content' if dup else 'downloaded'; seen_hash.setdefault(digest,str(path.relative_to(ROOT)))
   except Exception as e:
    if path.exists(): path.unlink()
    records.append({'status':'failed','site':seed['site'],'source_url':pdf,'index_page':page,'term':t,'error':str(e)}); continue
   records.append({'status':status,'site':seed['site'],'source_suffix':seed['suffix'],'source_url':pdf,'index_page':page,'original_filename':Path(urlparse(pdf).path).name,'anchor_text':anchor,'academic_year':(YEAR.search(' '.join([anchor,ctx,page,pdf])) or [None])[0],'term':t,'document_type':'correction' if corr else 'devoir_or_exam','branch_group':'common_or_scientific','subject':'french','level':'3AS','sha256':digest,'local_path':str(path.relative_to(ROOT)),'duplicate_of':dup})
   time.sleep(.05)
 MANIFEST.write_text(json.dumps({'schema_version':'1.3','subject':'french','level':'3AS','branch_group':'common_or_scientific','generated_by':'tools/import_french_scientific.py','sources':[x['url'] for x in SEEDS],'count':len(records),'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
