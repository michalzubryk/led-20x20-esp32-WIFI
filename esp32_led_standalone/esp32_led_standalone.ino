// ESP32-WROOM/D0WD, Arduino-ESP32 3.x. USB frames + DDP over Wi-Fi.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp32-hal-rmt.h"
#include "wifi_secrets.h"

constexpr int DATA_PIN = 18;
constexpr size_t LEDS = 400, BYTES = LEDS * 3;
static uint8_t pixels[BYTES];
static rmt_data_t wave[LEDS * 24 + 1];
static WiFiUDP ddp, control;
static bool pending = false, ready = false, networkUp = false;
static uint32_t serialFrames = 0, udpFrames = 0, shown = 0, bad = 0, skipped = 0;
static uint32_t lastUs = 0, maxUs = 0, lastSequence = 0;
static uint64_t totalUs = 0;
static uint8_t serialBody[4 + BYTES + 4]; // seq LE32, pixels, CRC32(seq+pixels)
static size_t serialPos = 0, magicPos = 0;
static bool receiving = false, binaryMode = false;
static uint32_t lastByteMs = 0;
static const uint8_t magic[4] = {'L','4','0','0'};

uint32_t crc32(const uint8_t *p, size_t n) {
  uint32_t c = 0xffffffff;
  while (n--) {
    c ^= *p++;
    for (int k=0;k<8;++k) c = (c >> 1) ^ (0xedb88320u & (0u - (c & 1)));
  }
  return ~c;
}
uint32_t le32(const uint8_t *p) {
  return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
void markPending() {
  if (pending) ++skipped;
  pending = true;
}
String stats() {
  char buf[420];
  snprintf(buf,sizeof(buf),
    "{\"ip\":\"%s\",\"wifi\":%s,\"uptime_ms\":%lu,\"serial_rx\":%lu,\"udp_rx\":%lu,\"shown\":%lu,\"bad\":%lu,\"skipped\":%lu,\"last_sequence\":%lu,\"last_show_us\":%lu,\"max_show_us\":%lu,\"avg_show_us\":%llu}",
    WiFi.localIP().toString().c_str(), WiFi.status()==WL_CONNECTED?"true":"false",
    (unsigned long)millis(),(unsigned long)serialFrames,(unsigned long)udpFrames,
    (unsigned long)shown,(unsigned long)bad,(unsigned long)skipped,(unsigned long)lastSequence,
    (unsigned long)lastUs,(unsigned long)maxUs,(unsigned long long)(shown?totalUs/shown:0));
  return String(buf);
}
void show() {
  uint32_t start = micros();
  size_t pos=0;
  for (uint8_t channel : pixels) {
    for (uint8_t mask=128;mask;mask>>=1) {
      bool one=channel&mask;
      wave[pos].level0=1; wave[pos].duration0=one?30:10;
      wave[pos].level1=0; wave[pos].duration1=one?10:30;
      ++pos;
    }
  }
  wave[pos].level0=0; wave[pos].duration0=12000;
  wave[pos].level1=0; wave[pos].duration1=12000;
  if (rmtWrite(DATA_PIN,wave,pos+1,RMT_WAIT_FOR_EVER)) {
    lastUs=micros()-start; maxUs=max(maxUs,lastUs); totalUs+=lastUs; ++shown;
  } else ++bad;
  pending=false;
}
#include "generator.h"
void serialInput() {
  if (millis()-lastByteMs>250) {
    if (receiving||magicPos) ++bad;
    receiving=false;magicPos=0;serialPos=0;binaryMode=false;
  }
  // Bounded work prevents continuous serial traffic starving Wi-Fi/rendering.
  uint8_t chunk[512];
  unsigned budget=4096;
  while (budget && Serial.available()) {
    size_t count=min(size_t(Serial.available()),min(sizeof(chunk),size_t(budget)));
    count=Serial.read(chunk,count);budget-=count;
    if (!count) break;
    lastByteMs=millis();
    for (size_t index=0;index<count;++index) {
    uint8_t c=chunk[index];
    if (receiving) {
      serialBody[serialPos++]=c;
      if (serialPos==sizeof(serialBody)) {
        if (crc32(serialBody,4+BYTES)==le32(serialBody+4+BYTES)) {
          if(cfg.source=="stream") { memcpy(pixels,serialBody+4,BYTES);lastSequence=le32(serialBody);
          ++serialFrames;markPending(); }
          receiving=false;magicPos=0;serialPos=0;
        } else {
          ++bad;
          // Recover after a missing/extra byte, without requiring the stream to stop.
          size_t next=0;
          for (;next+4<=sizeof(serialBody);++next)
            if (!memcmp(serialBody+next,magic,4)) break;
          if (next+4<=sizeof(serialBody)) {
            serialPos=sizeof(serialBody)-next-4;
            memmove(serialBody,serialBody+next+4,serialPos);
          } else {
            receiving=false;magicPos=0;serialPos=0;
            for (size_t count=1;count<4;++count)
              if (!memcmp(serialBody+sizeof(serialBody)-count,magic,count)) magicPos=count;
          }
        }
      }
    } else if (c==magic[magicPos]) {
      if (++magicPos==4) { receiving=true;binaryMode=true;serialPos=0;magicPos=0; }
    } else {
      bool idle=(magicPos==0 && !binaryMode);magicPos=(c==magic[0])?1:0;
      if (idle && c=='i') Serial.println(stats());
      if (idle && c=='0') { cfg.enabled=false;publishRemoteSettings(); memset(pixels,0,BYTES);markPending(); }
      if (idle && c=='f') { cfg.enabled=false;publishRemoteSettings();
        memset(pixels,0,BYTES);memset(pixels,16,20*3);markPending();
      }
    }
    }
  }
}
void networkInput() {
  bool connected=WiFi.status()==WL_CONNECTED;
  if (connected && !networkUp) {
    networkUp=ddp.begin(4048) && control.begin(4049);
    configTime(0,0,"pool.ntp.org","time.google.com","time.cloudflare.com");
    Serial.println(stats());
  } else if (!connected && networkUp) {
    ddp.stop();control.stop();networkUp=false;
  }
  if (!networkUp) return;
  static uint8_t packet[10+BYTES];
  for (unsigned budget=0;budget<8;++budget) {
    int n=ddp.parsePacket();if (!n) break;
    if (n<10 || n>int(sizeof(packet))) { ddp.clear();++bad;continue; }
    if (ddp.read(packet,n)!=n) { ++bad;continue; }
    uint32_t offset=uint32_t(packet[4])<<24|uint32_t(packet[5])<<16|uint32_t(packet[6])<<8|packet[7];
    uint16_t length=uint16_t(packet[8])<<8|packet[9];
    // DDP v1, RGB24, display 1, no query/reply/timecode, bounded offsets.
    if ((packet[0]&0xfe)!=0x40 || (packet[2]!=0x0b && packet[2]!=0) ||
        packet[3]!=1 || length!=n-10 || offset>BYTES || length>BYTES-offset) {
      ++bad;continue;
    }
    if(cfg.source!="stream") continue;
    memcpy(pixels+offset,packet+10,length);
    if (packet[0]&1) { ++udpFrames;markPending(); }
  }
  int n=control.parsePacket();
  if (n) {
    char request[16]={0};control.read((uint8_t*)request,sizeof(request)-1);control.clear();
    if (!strcmp(request,"stats")) {
      String reply=stats();control.beginPacket(control.remoteIP(),control.remotePort());
      control.write((const uint8_t*)reply.c_str(),reply.length());control.endPacket();
    }
  }
}
void setup() {
  Serial.setRxBufferSize(32768); Serial.begin(921600);
  Serial.setRxFIFOFull(32);Serial.setRxTimeout(1);delay(500);
  pinMode(DATA_PIN,OUTPUT);digitalWrite(DATA_PIN,LOW);
  ready=rmtInit(DATA_PIN,RMT_TX_MODE,RMT_MEM_NUM_BLOCKS_4,40000000);
  if (!ready || !rmtSetEOT(DATA_PIN,LOW)) {
    ready=false;Serial.println("ERROR RMT INIT");return;
  }
  memset(pixels,16,20*3);show();
  WiFi.persistent(false);WiFi.setHostname("led400");WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);WiFi.setAutoReconnect(true);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  setupGenerator();
  Serial.println("LED400 STANDALONE v2 remote+OTA GPIO18 serial=921600 DDP=4048 stats=4049; i=stats f=first20 0=off");
}
void loop() {
  if (!ready) { delay(100);return; }
  serialInput();networkInput();generatorLoop();if (pending) show();delay(1);
}
