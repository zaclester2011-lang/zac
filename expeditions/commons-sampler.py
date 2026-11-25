import sys,json,subprocess,os,colorsys
from PIL import Image
UA="crete-trip-planner/1.0"
def cls(h,s):
    if s<0.12: return 'grey'
    if h<145: return 'green'
    if h<168: return 'emerald'
    if h<194: return 'TURQUOISE'
    if h<207: return 'blue-green'
    if h<227: return 'plain blue'
    return 'deep blue'
for arg in sys.argv[1:]:
    lab,q=arg.split("=",1)
    out=f"cm/{lab}"; os.makedirs(out,exist_ok=True)
    api=("https://commons.wikimedia.org/w/api.php?action=query&generator=search"
         f"&gsrsearch={q}&gsrnamespace=6&gsrlimit=20&prop=imageinfo"
         "&iiprop=url&iiurlwidth=1200&format=json")
    raw=subprocess.run(["curl","-sL","--max-time","30","-A",UA,api],
                       capture_output=True,text=True,errors="ignore").stdout
    try: pages=json.loads(raw).get("query",{}).get("pages",{})
    except Exception: pages={}
    print(f"== {lab}  ({len(pages)} results)")
    n=0
    for pid,pg in pages.items():
        ii=pg.get("imageinfo",[{}])[0]
        u=ii.get("thumburl") or ii.get("url")
        if not u: continue
        title=pg.get("title","").replace("File:","")
        p=f"{out}/{n:02d}.jpg"
        subprocess.run(["curl","-sL","--max-time","25","-A",UA,u,"-o",p],capture_output=True)
        if not os.path.exists(p) or os.path.getsize(p)<40000:
            os.path.exists(p) and os.remove(p); continue
        try:
            im=Image.open(p).convert("RGB"); w,h=im.size
            im2=im.resize((200,max(1,int(200*h/w)))); px=list(im2.getdata())
            body=px[int(len(px)*0.25):]
            wat=[]
            for r,g,b in body:
                hh,ss,vv=colorsys.rgb_to_hsv(r/255,g/255,b/255)
                if ss<0.10 or max(r,g,b)<60: continue
                if 100<=hh*360<=260: wat.append((hh*360,ss,vv,(r,g,b)))
            frac=len(wat)/max(1,len(body))
            if frac<0.12:
                os.remove(p); continue
            wat.sort(key=lambda t:-t[2])
            hx=wat[min(len(wat)//20,len(wat)-1)]
            print(f"   {p} water~{frac*100:4.1f}% #{hx[3][0]:02X}{hx[3][1]:02X}{hx[3][2]:02X} {cls(hx[0],hx[1]):11s} {title[:52]}")
            n+=1
        except Exception:
            os.path.exists(p) and os.remove(p)
        if n>=6: break
