#include <WebServer.h>
#include <Preferences.h>
#include "font.h"
#include "page.h"
#include "remote_secrets.h"
WebServer web(80);
Preferences prefs;
struct Settings {
  String source="local";
  String text="HELLO 123", mode="text", direction="left", color="00ccff", layout="columns", order="RGB";
  int speed=10, brightness=24, scale=1, start=0, blinkMs=500;
  bool enabled=true, blink=false, invert=false;
} cfg;
uint32_t epoch=0,lastGenerated=0;
uint8_t preview[1200];
String escapeJson(const String &s) {
  String out;
  for(size_t i=0;i<s.length();i++) {
    char c=s[i];
    if(c=='"' || c=='\\') {out+='\\';out+=c;}
    else if(uint8_t(c)<32) out+=' ';
    else out+=c;
  }
  return out;
}
String configJson() {
  return "{\"source\":\""+cfg.source+"\",\"text\":\""+escapeJson(cfg.text)+"\",\"mode\":\""+cfg.mode+
    "\",\"direction\":\""+cfg.direction+"\",\"color\":\"#"+cfg.color+
    "\",\"layout\":\""+cfg.layout+"\",\"order\":\""+cfg.order+
    "\",\"speed\":"+cfg.speed+",\"brightness\":"+cfg.brightness+
    ",\"scale\":"+cfg.scale+",\"start\":"+cfg.start+",\"blinkMs\":"+cfg.blinkMs+
    ",\"enabled\":"+(cfg.enabled?"true":"false")+",\"blink\":"+(cfg.blink?"true":"false")+
    ",\"invert\":"+(cfg.invert?"true":"false")+"}";
}
void persist(bool write) {
#define STR(name) if(write) prefs.putString(#name,cfg.name); else cfg.name=prefs.getString(#name,cfg.name)
#define NUM(name) if(write) prefs.putInt(#name,cfg.name); else cfg.name=prefs.getInt(#name,cfg.name)
#define BOOL(name) if(write) prefs.putBool(#name,cfg.name); else cfg.name=prefs.getBool(#name,cfg.name)
  STR(source);STR(text);STR(mode);STR(direction);STR(color);STR(layout);STR(order);
  NUM(speed);NUM(brightness);NUM(scale);NUM(start);NUM(blinkMs);
  BOOL(enabled);BOOL(blink);BOOL(invert);
#undef STR
#undef NUM
#undef BOOL
}
bool choice(String v,const char *opts) {return String(opts).indexOf("|"+v+"|")>=0;}
bool integerArg(const char *key,int low,int high,int &target) {
  if(!web.hasArg(key)) return true;
  String s=web.arg(key);
  if(!s.length() || s.length()>7) return false;
  for(char c:s) if(c<'0'||c>'9') return false;
  long n=s.toInt();if(n<low||n>high)return false;
  target=n;return true;
}
#include "remote.h"
void configure() {
  Settings old=cfg;
  bool valid=true;
  if(web.hasArg("text")) {cfg.text=web.arg("text");valid &= cfg.text.length()<=240;}
#define SELECT(name,choices) if(web.hasArg(#name)) {cfg.name=web.arg(#name);valid &= choice(cfg.name,choices);}
  SELECT(source,"|local|server|stream|");
  SELECT(mode,"|text|counter|rainbow|bars|pulse|bounce|");
  SELECT(direction,"|left|right|up|down|none|");
  SELECT(layout,"|columns|columns-serpentine|rows|rows-serpentine|");
  SELECT(order,"|RGB|GRB|RBG|GBR|BRG|BGR|");
#undef SELECT
  if(web.hasArg("color")) {
    cfg.color=web.arg("color");if(cfg.color.startsWith("#")) cfg.color.remove(0,1);
    valid &= cfg.color.length()==6;
    for(char c:cfg.color) valid &= (isxdigit(c)!=0);
  }
  valid &= integerArg("speed",1,40,cfg.speed);
  valid &= integerArg("brightness",0,255,cfg.brightness);
  valid &= integerArg("scale",1,2,cfg.scale);
  valid &= integerArg("start",0,999999,cfg.start);
  valid &= integerArg("blinkMs",100,2000,cfg.blinkMs);
#define BOOLARG(name) if(web.hasArg(#name)) {String v=web.arg(#name);valid &= v=="true"||v=="false";cfg.name=v=="true";}
  BOOLARG(enabled);BOOLARG(blink);BOOLARG(invert);
#undef BOOLARG
  if(!valid) {cfg=old;web.send(400,"application/json","{\"error\":\"Niepoprawne ustawienia\"}");return;}
  epoch=millis();
  publishRemoteSettings();
  // Persist only explicit Save / Start / Stop, not repeated preview changes.
  if(web.arg("save")=="true") persist(true);
  if(!cfg.enabled) {memset(pixels,0,BYTES);memset(preview,0,sizeof(preview));markPending();}
  web.send(200,"application/json",configJson());
}
const Glyph *findGlyph(uint32_t c) {
  for(const Glyph &g:glyphs) if(g.code==c) return &g;
  return &glyphs['?'-32];
}
uint32_t nextCode(const String &s,size_t &i) {
  uint8_t c=s[i++];
  if(c<128)return c;
  int n=(c&0xe0)==0xc0?1:(c&0xf0)==0xe0?2:(c&0xf8)==0xf0?3:0;
  if(!n)return '?';
  uint32_t value=c&((1<<(6-n))-1);
  while(n--) {
    if(i>=s.length() || (uint8_t(s[i])&0xc0)!=0x80)return '?';
    value=(value<<6)|(uint8_t(s[i++])&63);
  }
  return value;
}
void generateFrame(uint32_t now) {
  float t=(now-epoch)/1000.0f;
  memset(preview,0,sizeof(preview));
  uint32_t rgb=strtoul(cfg.color.c_str(),nullptr,16);
  uint8_t cr=rgb>>16,cg=rgb>>8,cb=rgb;
  const Glyph *letters[240];int count=0,width=0;
  if(cfg.mode=="text" || cfg.mode=="counter") {
    String text=cfg.mode=="text"?cfg.text:String(cfg.start+uint32_t(t));
    size_t i=0;
    while(i<text.length() && count<240) {
      const Glyph *g=findGlyph(nextCode(text,i));
      letters[count++]=g;width+=(g->width+1)*cfg.scale;
    }
    if(width)width-=cfg.scale;
  }
  int height=10*cfg.scale,ox=(20-width)/2,oy=(20-height)/2;
  int movement=int(t*cfg.speed);
  if(cfg.direction=="left") ox=20-movement%max(1,20+width);
  if(cfg.direction=="right") ox=-width+movement%max(1,20+width);
  if(cfg.direction=="up") oy=20-movement%(20+height);
  if(cfg.direction=="down") oy=-height+movement%(20+height);
  // Vertical and static text is centered. Use short text or small font to fit width.
  bool dark=cfg.blink && ((now-epoch)/cfg.blinkMs)%2;
  for(int y=0;y<20;y++) for(int x=0;x<20;x++) {
    uint8_t r=0,g=0,b=0;
    if(cfg.mode=="text"||cfg.mode=="counter") {
      int tx=x-ox,ty=y-oy;
      if(tx>=0 && ty>=0 && ty<height) {
        for(int k=0;k<count;k++) {
          int gw=letters[k]->width*cfg.scale;
          if(tx<gw) {
            if(letters[k]->rows[ty/cfg.scale]&(1<<(tx/cfg.scale))) {r=cr;g=cg;b=cb;}
            break;
          }
          tx-=gw+cfg.scale;
          if(tx<0)break;
        }
      }
    } else {
      int dx=0,dy=0;
      if(cfg.direction=="left")dx=movement;
      if(cfg.direction=="right")dx=-movement;
      if(cfg.direction=="up")dy=movement;
      if(cfg.direction=="down")dy=-movement;
      if(cfg.mode=="rainbow") {
        float h=fmodf((x+dx)/20.0f+(y+dy)/40.0f+10000,1)*6;
        int segment=int(h);float f=h-segment;
        uint8_t a=255*(1-f),v=255*f;
        switch(segment){case 0:r=255;g=v;break;case 1:r=a;g=255;break;case 2:g=255;b=v;break;case 3:g=a;b=255;break;case 4:r=v;b=255;break;default:r=255;b=a;}
      } else if(cfg.mode=="bars") {
        if(((x+dx+y+dy)%20+20)%20<3){r=cr;g=cg;b=cb;}
      } else if(cfg.mode=="pulse") {
        float f=cfg.direction=="none"?1:(sinf(t*cfg.speed/5)+1)/2;
        r=cr*f;g=cg*f;b=cb*f;
      } else if(cfg.mode=="bounce") {
        int bx=8,by=8;
        if(cfg.direction=="left"||cfg.direction=="right")bx=round(8+8*sinf((cfg.direction=="left"?-1:1)*t*cfg.speed/10));
        if(cfg.direction=="up"||cfg.direction=="down")by=round(8+8*sinf((cfg.direction=="up"?-1:1)*t*cfg.speed/10));
        if(x>=bx && x<bx+4 && y>=by && y<by+4){r=cr;g=cg;b=cb;}
      }
    }
    if(cfg.invert){r=255-r;g=255-g;b=255-b;}
    if(dark){r=g=b=0;}
    int at=(y*20+x)*3;preview[at]=r;preview[at+1]=g;preview[at+2]=b;
    int led=cfg.layout=="columns"?x*20+y:
      cfg.layout=="columns-serpentine"?x*20+(x%2?19-y:y):
      cfg.layout=="rows"?y*20+x:y*20+(y%2?19-x:x);
    uint8_t colors[3]={r,g,b};
    for(int c=0;c<3;c++) {
      int channel=cfg.order[c]=='R'?0:cfg.order[c]=='G'?1:2;
      pixels[led*3+c]=uint16_t(colors[channel])*cfg.brightness/255;
    }
  }
  markPending();
}
void setupGenerator() {
  prefs.begin("led-generator",false);persist(false);epoch=millis();
  web.on("/",HTTP_GET,[]{web.send_P(200,"text/html; charset=utf-8",PAGE);});
  web.on("/api/config",HTTP_GET,[]{web.send(200,"application/json",configJson());});
  web.on("/api/config",HTTP_POST,configure);
  web.on("/api/stats",HTTP_GET,[]{web.send(200,"application/json",stats());});
  web.on("/preview",HTTP_GET,[]{
    web.sendHeader("Cache-Control","no-store");
    web.setContentLength(sizeof(preview));
    web.send(200,"application/octet-stream","");
    web.sendContent((const char*)preview,sizeof(preview));
  });
  setupRemote();
  web.begin();
}
void generatorLoop() {
  web.handleClient();
  uint32_t now=millis();
  if(rebootAt.load() && int32_t(now-rebootAt.load())>=0) ESP.restart();
  if(otaBusy.load())return;
  fallbackActive=false;
  if(cfg.source=="server" && cfg.enabled) {
    // A stalled remote stream must never switch to the saved local effect.
    // Keep the last complete frame (black until the first frame after boot).
    consumeRemoteFrame();
    fallbackActive=!(remoteLastMs.load() && now-remoteLastMs.load()<3000);
    return;
  }
  if(cfg.enabled && cfg.source!="stream" && now-lastGenerated>=33) {lastGenerated=now;generateFrame(now);}
}
