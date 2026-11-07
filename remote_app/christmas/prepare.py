"""Download OpenMoji artwork and encode it for the existing 20x20 RGB protocol."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
ICONS=[("1F384","Choinka"),("1F385","Mikołaj"),("1F381","Prezent"),
       ("26C4","Bałwan"),("2744","Śnieżynka"),("1F514","Dzwonek"),
       ("1F31F","Gwiazdka"),("1F56F","Świeca"),("1F98C","Jelonek"),("1F9E6","Skarpety")]
BASE="https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/"
def download(item):
    code,name=item;url=BASE+"color/618x618/"+code+".png"
    path=ROOT/"originals"/(code+".png")
    if not path.exists():
        with urllib.request.urlopen(url,timeout=30) as r:path.write_bytes(r.read())
    with Image.open(path) as image:
        image=image.convert("RGBA")
        if code=="2744":
            # A black line icon would be invisible on an LED matrix's black background.
            alpha=image.getchannel("A");image=Image.new("RGBA",image.size,"white");image.putalpha(alpha)
        image=image.crop(image.getchannel("A").getbbox())
        image.thumbnail((18,18),Image.Resampling.LANCZOS)
        canvas=Image.new("RGB",(20,20))
        canvas.paste(image,((20-image.width)//2,(20-image.height)//2),image.getchannel("A"))
        frame=list(canvas.tobytes())
        canvas.save(ROOT/(code+"-20.png"))
    return {"name":"Święta · "+name,"frames":[frame],"durationMs":1000},dict(code=code,name=name,source=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def main():
    (ROOT/"originals").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(download,ICONS))
    shapes=[s for s,_ in results]
    shapes.append(dict(name="Święta · Pokaz wszystkich",frames=[s["frames"][0] for s in shapes],durationMs=1500))
    (ROOT/"shapes.json").write_text(json.dumps(shapes,ensure_ascii=False))
    (ROOT/"sources.json").write_text(json.dumps([s for _,s in results],ensure_ascii=False,indent=2))
    with urllib.request.urlopen(BASE+"LICENSE.txt",timeout=30) as r:(ROOT/"LICENSE.txt").write_bytes(r.read())
    # Contact sheet is a review artifact, not used to drive LEDs.
    sheet=Image.new("RGB",(500,240),"#172132");d=ImageDraw.Draw(sheet)
    for i,(code,name) in enumerate(ICONS):
        im=Image.open(ROOT/(code+"-20.png")).resize((80,80),Image.Resampling.NEAREST)
        x=(i%5)*100+10;y=(i//5)*120+5
        sheet.paste(im,(x,y));d.text((x,y+85),name,fill="white")
    sheet.save(ROOT/"contact-sheet.png")
    print("Prepared",len(shapes),"shapes (10 static + slideshow)")
if __name__=="__main__":main()
