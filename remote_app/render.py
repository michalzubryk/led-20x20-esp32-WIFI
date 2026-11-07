import colorsys
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

FONT=json.loads(Path(__file__).with_name("font.json").read_text())
DEFAULT=dict(mode="text",text="HELLO 123",direction="left",speed=10,color="#00ccff",
             brightness=24,scale=1,start=0,blink=False,blinkMs=500,invert=False,
             enabled=True,shapeId="",animate=True)
CHOICES={"mode":{"text","counter","rainbow","bars","pulse","bounce","custom"},
         "direction":{"left","right","up","down","none"}}
def validate_scene(data,previous):
    if not isinstance(data,dict) or set(data)-set(DEFAULT):raise ValueError("Nieznane ustawienia")
    c={**previous,**data}
    for key,choices in CHOICES.items():
        if not isinstance(c[key],str) or c[key] not in choices:raise ValueError(key)
    for key,limits in {"speed":(1,40),"brightness":(0,255),"scale":(1,2),"start":(0,999999),"blinkMs":(100,2000)}.items():
        if type(c[key]) is not int or not limits[0]<=c[key]<=limits[1]:raise ValueError(key)
    for key in ("blink","invert","enabled","animate"):
        if type(c[key]) is not bool:raise ValueError(key)
    if not isinstance(c["text"],str) or len(c["text"].encode())>240:raise ValueError("Tekst za długi (240 bajtów)")
    if not isinstance(c["shapeId"],str) or len(c["shapeId"])>64:raise ValueError("Kształt")
    import re
    if not isinstance(c["color"],str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",c["color"]):raise ValueError("Kolor")
    return c

def text_image(text,scale,color):
    glyphs=[FONT.get(c,FONT["?"]) for c in text]
    width=max(1,sum(g["width"]+1 for g in glyphs)-1)
    im=Image.new("RGB",(width,10))
    x=0
    for g in glyphs:
        for y,row in enumerate(g["rows"]):
            for dx in range(g["width"]):
                if row&(1<<dx):im.putpixel((x+dx,y),color)
        x+=g["width"]+1
    return im.resize((width*scale,10*scale),Image.Resampling.NEAREST)

def render(c,t,shapes):
    im=Image.new("RGB",(20,20));draw=ImageDraw.Draw(im)
    if not c["enabled"]:return bytes(1200)
    color=tuple(bytes.fromhex(c["color"][1:]));m=int(t*c["speed"]);direction=c["direction"]
    if c["mode"] in ("text","counter","custom"):
        if c["mode"]=="custom":
            shape=shapes.get(c["shapeId"])
            if not shape:return bytes(1200)
            frames=shape["frames"];index=int(t*1000/shape["durationMs"])%len(frames) if c["animate"] else 0
            tile=Image.frombytes("RGB",(20,20),bytes(frames[index]))
        else:
            text=c["text"] if c["mode"]=="text" else str(c["start"]+int(t))
            tile=text_image(text,c["scale"],color)
        x=(20-tile.width)//2;y=(20-tile.height)//2
        if direction=="left":x=20-m%(20+tile.width)
        if direction=="right":x=-tile.width+m%(20+tile.width)
        if direction=="up":y=20-m%(20+tile.height)
        if direction=="down":y=-tile.height+m%(20+tile.height)
        im.paste(tile,(x,y))
    elif c["mode"]=="bounce":
        x=y=8
        if direction in ("left","right"):x=round(8+8*math.sin((-1 if direction=="left" else 1)*t*c["speed"]/10))
        if direction in ("up","down"):y=round(8+8*math.sin((-1 if direction=="up" else 1)*t*c["speed"]/10))
        draw.rectangle((x,y,x+3,y+3),fill=color)
    elif c["mode"]=="pulse":
        f=1 if direction=="none" else (math.sin(t*c["speed"]/5)+1)/2
        draw.rectangle((0,0,19,19),fill=tuple(int(v*f) for v in color))
    else:
        dx=m if direction=="left" else -m if direction=="right" else 0
        dy=m if direction=="up" else -m if direction=="down" else 0
        for y in range(20):
            for x in range(20):
                if c["mode"]=="rainbow":v=tuple(int(v*255) for v in colorsys.hsv_to_rgb(((x+dx)/20+(y+dy)/40)%1,1,1))
                else:v=color if (x+dx+y+dy)%20<3 else (0,0,0)
                im.putpixel((x,y),v)
    frame=im.tobytes()
    if c["invert"]:frame=bytes(255-v for v in frame)
    if c["blink"] and int(t*1000/c["blinkMs"])%2:return bytes(1200)
    return bytes(v*c["brightness"]//255 for v in frame)
