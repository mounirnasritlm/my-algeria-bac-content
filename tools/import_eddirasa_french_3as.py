from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from urllib.parse import parse_qs,unquote,urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BASE='https://eddirasa.com/ens-sec/3as/francais/'
OUT=ROOT/'content/3as/branches/_shared/subjects/french'
RAW=OUT/'resources'; EXTRACTED=OUT/'extracted'; MANIFEST=OUT/'source_metadata'/'eddirasa_3as_french.json'
HEAD={'User-Agent':'Mozilla/5.0 (MY Algeria BAC content importer)'}
ALLOWED={'.pdf','.doc','.docx','.ppt','.pptx','.xls','.xlsx','.zip','.rar'}
TERM=[('first_term',re.compile(r'premier|1er|term[ei]?[- ]?1|الفصل\s*(?:الأول|1)',re.I)),('second_term',re.compile(r'deuxi|2[eè]me|term[ei]?[- ]?2|الفصل\s*(?:الثاني|2)',re.I)),('third_term',re.compile(r'troisi|3[eè]me|term[ei]?[- ]?3|الفصل\s*(?:الثالث|3)',re.I))]
CORR=re.compile(r'corrig|correction|solution|حل|تصحيح',re.I)
s=requests.Session(); s.headers.update(HEAD)

def clean(x):
 x=re.sub(r'\s+',' ',x.strip()); x=re.sub(r'[\\/:*?"<>|]+','-',x); return re.sub(r'-+','-',x).strip(' .-')[:180] or 'document'
def inside(u):
 p=urlparse(u); return p.netloc.lower().endswith('eddirasa.com') and p.path.startswith('/ens-sec/3as/francais/')
def embedded(u):
 p=urlparse(u)
 if p.path.lower().endswith(tuple(ALLOWED)): return u
 for k in ('file','pdf','url','src','document','download'):
  for v in parse_qs(p.query).get(k,[]):
   v=unquote(v)
   if urlparse(v).path.lower().endswith(tuple(ALLOWED)): return urljoin(u,v)
 return None
def get_term(text,default='unspecified'):
 for name,p in TERM:
  if p.search(text): return name
 return default
def fetch(url):
 r=s.get(url,timeout=45,allow_redirects=True); r.raise_for_status(); return r.text,r.url
def category(label,url,ctx):
 t=' '.join([label,url,ctx]).lower()
 checks=[('curriculum_programme',['برنامج','programme','program']),('courses_lessons',['دروس وملخصات','cours','lesson']),('summaries',['ملخصات','résumé','resume']),('teacher_books',['كتب الأساتذة','livre professeur','teacher']),('school_books',['الكتب المدرسية','livres scolaires']),('external_books',['كتب خارجية','livres externes']),('notes',['مذكرات','notes','memoire']),('pedagogical_files',['ملفات بيداغوجية','pédagog']),('school_tools',['قائمة الأدوات','outils scolaires']),('language_enrichment',['إثراء الرصيد','enrichissement']),('language_by_images',['تعلم اللغة الفرنسية بالصور','images']),('communication_techniques',['تقنيات الاتصال','communication']),('grammar',['قواعد اللغة','grammaire']),('devoirs',['فروض','devoir']),('tests_exams',['اختبارات','exam','test'])]
 for name,keys in checks:
  if any(k in t for k in keys): return name
 return 'other'
def group(label,url,ctx):
 t=' '.join([label,url,ctx]).lower()
 if 'شعب علمية' in t or 'scientifique' in t or 'science' in t: return 'common_or_scientific'
 if 'شعب أدبية' in t or 'littéraire' in t or 'adab' in t: return 'literary'
 return 'common'
def crawl():
 seen=set(); q=[(BASE,0,'','common','unspecified')]; found={}
 while q:
  page,depth,label,grp,inherited_term=q.pop(0)
  if page in seen or depth>3: continue
  seen.add(page)
  try: html,final=fetch(page)
  except Exception as e: print('WARN',page,e); continue
  soup=BeautifulSoup(html,'html.parser'); title=soup.title.get_text(' ',strip=True) if soup.title else ''; text=soup.get_text(' ',strip=True)
  cat=category(label or title,final,text[:2000]); grp2=group(label or title,final,text[:2000]); t=get_term(' '.join([label,title,text[:2000]]),inherited_term)
  for el in soup.find_all(['a','iframe','embed','object','source']):
   raw=[]
   for a in ('href','src','data','data-href','data-url','data-pdf','onclick'):
    if el.get(a): raw.append(str(el.get(a)))
   anchor=el.get_text(' ',strip=True); ctx=' '.join([anchor, title, el.parent.get_text(' ',strip=True) if el.parent else ''])
   for raw_url in raw:
    u=urljoin(final,raw_url); e=embedded(u); k=' '.join([anchor,ctx,u])
    if e:
     found[e]={'anchor':anchor,'context':ctx,'index_page':final,'category':cat,'group':grp2,'term':get_term(k,t),'has_correction':bool(CORR.search(k))}; continue
    if depth<3 and inside(u) and not any(x in u.lower() for x in ['privacy','contact','login','comment','tag/']): q.append((u,depth+1,anchor or label,grp2,t))
  for m in re.findall(r'https?://[^\"\'<>\s]+\.(?:pdf|docx?|pptx?|xlsx?|zip|rar)(?:\?[^\"\'<>\s]*)?',html,re.I):
   found[m]={'anchor':'','context':title,'index_page':final,'category':cat,'group':grp2,'term':t,'has_correction':bool(CORR.search(title+' '+text[:2000]))}
 return found
def folder(rec):
 base=RAW/rec['group']
 if rec['category'] in {'devoirs','tests_exams'}: return base/rec['category']/rec['term']
 return base/rec['category']
def name(url,anchor,used):
 p=urlparse(url); stem=clean(unquote(Path(p.path).stem) or anchor or 'document'); ext=Path(p.path).suffix.lower() or '.pdf'; base=f'{stem}__eddirasa'; n=base+ext
 if n in used: n=f'{base}__{hashlib.sha256(url.encode()).hexdigest()[:8]}{ext}'
 used.add(n); return n
def extract_pdf(src,dst):
 try:
  from pypdf import PdfReader
  r=PdfReader(str(src)); pages=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(r.pages)]
  data={'schema_version':'1.0','source_file':str(src.relative_to(ROOT)),'extraction_status':'success','page_count':len(pages),'pages':pages}
 except Exception as e: data={'schema_version':'1.0','source_file':str(src.relative_to(ROOT)),'extraction_status':'failed','error':str(e)}
 dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 found=crawl(); print('Discovered attachments:',len(found)); records=[]; used=set(); hashes={}
 for url,rec in sorted(found.items()):
  d=folder(rec); d.mkdir(parents=True,exist_ok=True); path=d/name(url,rec['anchor'],used)
  try:
   r=s.get(url,timeout=120,stream=True,allow_redirects=True); r.raise_for_status(); c=(r.headers.get('content-type') or '').lower(); final=r.url; ext=Path(urlparse(final).path).suffix.lower()
   if ext not in ALLOWED and not any(x in c for x in ['pdf','word','officedocument','powerpoint','spreadsheet','zip','rar']): raise ValueError(f'unsupported attachment: {c} {final}')
   h=hashlib.sha256(); total=0
   with path.open('wb') as f:
    for ch in r.iter_content(1024*1024):
     if ch: h.update(ch); total+=len(ch); f.write(ch)
   digest=h.hexdigest(); dup=hashes.get(digest); hashes.setdefault(digest,str(path.relative_to(ROOT)))
   ej=None
   if path.suffix.lower()=='.pdf':
    ej=EXTRACTED/(path.relative_to(OUT)).with_suffix('.json'); extract_pdf(path,ej)
   records.append({'status':'duplicate_content' if dup else 'downloaded','site':'eddirasa','source_suffix':'eddirasa','source_url':url,'final_url':final,'index_page':rec['index_page'],'original_filename':Path(urlparse(url).path).name,'anchor_text':rec['anchor'],'category':rec['category'],'branch_group':rec['group'],'term':rec['term'],'has_correction':rec['has_correction'],'correction_mode':'embedded_in_same_file' if rec['has_correction'] else 'unknown','file_type':path.suffix.lower().lstrip('.'),'bytes':total,'sha256':digest,'local_path':str(path.relative_to(ROOT)),'extracted_json':str(ej.relative_to(ROOT)) if ej else None,'duplicate_of':dup})
  except Exception as e:
   if path.exists(): path.unlink()
   records.append({'status':'failed','site':'eddirasa','source_url':url,'index_page':rec['index_page'],'category':rec['category'],'branch_group':rec['group'],'term':rec['term'],'error':str(e)})
 MANIFEST.parent.mkdir(parents=True,exist_ok=True); MANIFEST.write_text(json.dumps({'schema_version':'2.0','source':BASE,'subject':'french','level':'3AS','scope':'scientific_and_literary','discovered_count':len(found),'record_count':len(records),'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
 from collections import Counter
 print('records=',len(records)); print('by_category=',dict(Counter(x.get('category') for x in records))); print('by_group=',dict(Counter(x.get('branch_group') for x in records))); print('failed=',sum(x.get('status')=='failed' for x in records))
if __name__=='__main__': main()
