"""Build OpenMoji Halloween images and animations for a 20x20 RGB display."""
from pathlib import Path
import hashlib,json,math,urllib.request
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
ICONS=[('1F383','Dynia'),('1F47B','Duch'),('1F987','Nietoperz'),('1F480','Czaszka'),('1F577','Pająk'),('1F578','Pajęczyna'),('1F56F','Świeczka')]
BASE='https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/'
def shape(name,frames,duration=200):
 return dict(name='Halloween · '+name,frames=[list(f.convert('RGB').tobytes()) for f in frames],durationMs=duration,kind='animation' if len(frames)>1 else 'image')
def main():
 (ROOT/'originals').mkdir(exist_ok=True)
 images={};sources=[];shapes=[]
 for code,name in ICONS:
  path=ROOT/'originals'/(code+'.png');url=BASE+code+'.png'
  if not path.exists():
   with urllib.request.urlopen(url,timeout=30) as r:path.write_bytes(r.read())
  im=Image.open(path).convert('RGBA');im=im.crop(im.getchannel('A').getbbox())
  if code in ('1F987','1F577','1F578'):
   # Dark silhouettes need a light tint to remain visible on an unlit matrix.
   alpha=im.getchannel('A');im=Image.new('RGBA',im.size,{'1F987':'#ab75ff','1F577':'#ff9050','1F578':'#bbddff'}[code]);im.putalpha(alpha)
  im.thumbnail((18,18),Image.Resampling.LANCZOS)
  canvas=Image.new('RGB',(20,20));canvas.paste(im,((20-im.width)//2,(20-im.height)//2),im)
  canvas.save(ROOT/(code+'-20.png'));images[name]=canvas;shapes.append(shape(name,[canvas],1000))
  sources.append(dict(code=code,name=name,source=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 # Pumpkin: carved eyes and mouth glow independently of the pumpkin body.
 frames=[];base=images['Dynia']
 for t in range(12):
  f=base.copy();d=ImageDraw.Draw(f);glow=int(100+155*(.5+.5*math.sin(t*math.tau/12)))
  d.polygon([(5,7),(8,8),(5,9)],fill=(255,glow,5));d.polygon([(14,7),(11,8),(14,9)],fill=(255,glow,5))
  d.line([(6,12),(8,14),(11,14),(13,12)],fill=(255,glow,5),width=1)
  frames.append(f)
 shapes.append(shape('Dynia — świecące oczy',frames,150))
 frames=[]
 for dy in [0,-1,-2,-1,0,1,2,1]:
  f=Image.new('RGB',(20,20));f.paste(images['Duch'],(0,dy));frames.append(f)
 shapes.append(shape('Duch — lewitowanie',frames,180))
 # An original pixel flame replaces only the flame area; the wax body remains.
 frames=[];base=images['Świeczka']
 for lean,height in [(0,0),(-1,1),(0,2),(1,0),(0,1),(-1,0),(1,2),(0,0)]:
  f=base.copy();d=ImageDraw.Draw(f);d.rectangle((6,0,13,8),fill='black')
  d.polygon([(9,8),(7,6),(8+lean,4),(10+lean,1+height),(12,6),(11,8)],fill='#ff6900')
  d.polygon([(9,8),(9,5),(10+lean,3+height),(11,7),(10,8)],fill='#ffdf40')
  d.point((10,7),fill='#fff4ba');frames.append(f)
 shapes.append(shape('Świeczka — migoczący płomień',frames,140))
 (ROOT/'shapes.json').write_text(json.dumps(shapes,ensure_ascii=False))
 (ROOT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
 sheet=Image.new('RGB',(600,260),'#172132');d=ImageDraw.Draw(sheet);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',10)
 for i,s in enumerate(shapes):
  x=(i%5)*120+10;y=(i//5)*130+5
  im=Image.frombytes('RGB',(20,20),bytes(s['frames'][0])).resize((100,100),Image.Resampling.NEAREST);sheet.paste(im,(x,y))
  d.text((x,y+102),s['name'].split(' · ')[1].split(' — ')[0]+(' *' if s['kind']=='animation' else ''),font=font,fill='white')
 sheet.save(ROOT/'contact-sheet.png')
 print('Prepared',len(shapes),'Halloween motifs')
if __name__=='__main__':main()
