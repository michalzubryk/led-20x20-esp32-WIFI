"""Generate small LED animation frames from the imported OpenMoji RGB assets."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
static={s["name"]:s["frames"][0] for s in json.loads((ROOT/"shapes.json").read_text())}
def pixel(frame,x,y,color):
    if 0<=x<20 and 0<=y<20:frame[(y*20+x)*3:(y*20+x)*3+3]=color
def at(frame,x,y):return frame[(y*20+x)*3:(y*20+x)*3+3]
def animation(name,frames,duration):
    assert len(frames)>1 and all(len(f)==1200 for f in frames)
    assert len({bytes(f) for f in frames})>1
    return dict(name="Święta · "+name,frames=frames,durationMs=duration,kind="animation")
def main():
    result=[]
    base=static["Święta · Choinka"]
    available=[(x,y) for y in range(5,18) for x in range(2,18)
               if at(base,x,y)[1]>45 and at(base,x,y)[1]>at(base,x,y)[0]*.8 and at(base,x,y)[1]>at(base,x,y)[2]*1.5]
    anchors=[]
    for tx,ty in [(9,5),(8,8),(12,10),(6,12),(10,13),(13,15),(8,16)]:
        chosen=min((p for p in available if p not in anchors),key=lambda p:(p[0]-tx)**2+(p[1]-ty)**2)
        anchors.append(chosen)
    colors=[(255,30,40),(20,170,255),(255,220,40),(255,70,200)]
    frames=[]
    for t in range(8):
        f=base.copy()
        for i,(x,y) in enumerate(anchors):
            if (t+i)%3:pixel(f,x,y,colors[(i+t//2)%len(colors)])
        frames.append(f)
    result.append(animation("Choinka — migające lampki",frames,250))
    base=static["Święta · Bałwan"];frames=[]
    for t in range(10):
        f=base.copy()
        for x,offset in [(2,1),(5,9),(14,3),(17,13),(1,16),(18,7)]:
            y=(offset+t*2)%20
            if max(at(base,x,y))<20:pixel(f,x,y,(150,210,255))
        frames.append(f)
    result.append(animation("Bałwan — padający śnieg",frames,200))
    base=static["Święta · Gwiazdka"];frames=[]
    for t in range(8):
        f=base.copy()
        for i,(x,y) in enumerate([(3,3),(16,4),(2,13),(16,16)]):
            phase=(t+i*2)%8
            if phase<3:pixel(f,x,y,(255,255,200))
            if phase==1:
                for dx,dy in [(0,1),(1,0),(0,-1),(-1,0)]:
                    if max(at(base,x+dx,y+dy))<20:pixel(f,x+dx,y+dy,(110,130,180))
        frames.append(f)
    result.append(animation("Gwiazdka — iskierki",frames,200))
    base=static["Święta · Świeca"];frames=[]
    for factor in [1,.6,.85,.5,.9,.7,1,.8]:
        f=base.copy()
        for y in range(9):
            for x in range(20):
                r,g,b=at(base,x,y)
                if r>50 and g>40 and b<r/2:pixel(f,x,y,(int(r*(.8+.2*factor)),int(g*factor),b))
        frames.append(f)
    result.append(animation("Świeca — żywy płomień",frames,200))
    (ROOT/"animated-shapes.json").write_text(json.dumps(result,ensure_ascii=False))
    print("Prepared",len(result),"animated motifs")
if __name__=="__main__":main()
