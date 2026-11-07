#pragma once
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <Update.h>
#include <atomic>
#include <time.h>
#include "mbedtls/sha256.h"
#include "remote_secrets.h"
#include "remote_ca.h"

static const char FW_VERSION[]="LED400 2.3 stream+OTA 2026-11-07";
static std::atomic<bool> remoteWanted(false),otaRequested(false),otaBusy(false);
static std::atomic<uint32_t> remoteFrames(0),remoteLastMs(0),rebootAt(0);
static portMUX_TYPE remoteMux=portMUX_INITIALIZER_UNLOCKED;
static uint8_t remotePixels[1200];
static uint32_t remoteGeneration=0;
static char remoteMessage[96]="Tryb lokalny",otaMessage[96]="Gotowe";
static bool fallbackActive=false;
static void setRemoteMessage(const char *s) {
  portENTER_CRITICAL(&remoteMux);strlcpy(remoteMessage,s,sizeof(remoteMessage));portEXIT_CRITICAL(&remoteMux);
}
static void setOtaMessage(const char *s) {
  portENTER_CRITICAL(&remoteMux);strlcpy(otaMessage,s,sizeof(otaMessage));portEXIT_CRITICAL(&remoteMux);
}
static String remoteStatus() {
  char message[96],ota[96];
  portENTER_CRITICAL(&remoteMux);strlcpy(message,remoteMessage,sizeof(message));strlcpy(ota,otaMessage,sizeof(ota));portEXIT_CRITICAL(&remoteMux);
  return "{\"source\":\""+cfg.source+"\",\"host\":\"https://" REMOTE_HOST ":"+String(REMOTE_PORT)+
    "\",\"frames\":"+String(remoteFrames.load())+",\"ageMs\":"+String(remoteLastMs.load()?millis()-remoteLastMs.load():0)+
    ",\"connected\":"+(remoteWanted.load() && remoteLastMs.load() && millis()-remoteLastMs.load()<3000?"true":"false")+
    ",\"fallback\":"+(fallbackActive?"true":"false")+",\"message\":\""+escapeJson(message)+
    "\",\"ota\":\""+escapeJson(ota)+"\",\"otaBusy\":"+(otaBusy.load()?"true":"false")+
    ",\"version\":\""+FW_VERSION+"\"}";
}
static void publishRemoteSettings() {
  bool wanted=cfg.source=="server" && cfg.enabled;
  if(wanted!=remoteWanted.load()) {
    remoteLastMs.store(0);
    remoteWanted.store(wanted);
  }
}
static bool validFirmwareHeader(const uint8_t *b,size_t n) {
  // ESP32 app image, not a merged bootloader image or another ESP family.
  return n>=24 && b[0]==0xe9 && b[12]==0 && b[13]==0;
}
// NetworkClient::readBytes stops on a transient TLS WANT_READ (-1).
// Wait for decrypted bytes explicitly so split TLS records do not truncate frames.
static size_t readTlsExact(NetworkClient *stream,uint8_t *buffer,size_t length,uint32_t timeoutMs,bool interruptible=false) {
  size_t count=0;uint32_t progress=millis();
  while(count<length && millis()-progress<timeoutMs) {
    if(interruptible && (!remoteWanted.load() || otaBusy.load()))break;
    int available=stream->available();
    if(available>0) {
      int n=stream->read(buffer+count,min(length-count,size_t(available)));
      if(n>0){count+=n;progress=millis();continue;}
    }
    if(!stream->connected())break;
    vTaskDelay(pdMS_TO_TICKS(2));
  }
  return count;
}
static void downloadFirmware() {
  setOtaMessage("Pobieranie firmware...");
  WiFiClientSecure client;client.setCACert(REMOTE_CA);client.setHandshakeTimeout(8);
  HTTPClient http;
  http.setConnectTimeout(5000);http.setTimeout(15000);
  String url="https://" REMOTE_HOST ":"+String(REMOTE_PORT)+"/api/device/firmware";
  if(!http.begin(client,url)) {setOtaMessage("Nie mozna otworzyc URL");return;}
  http.addHeader("Authorization","Bearer " DEVICE_TOKEN);
  const char *keys[]={"X-Firmware-SHA256"};http.collectHeaders(keys,1);
  int code=http.GET(),size=http.getSize();String expected=http.header("X-Firmware-SHA256");
  if(code!=200 || size<24 || expected.length()!=64) {char message[96];snprintf(message,sizeof(message),"Blad HTTPS OTA: HTTP %d, rozmiar %d, SHA %u",code,size,unsigned(expected.length()));http.end();setOtaMessage(message);return;}
  if(!Update.begin(size,U_FLASH)) {http.end();setOtaMessage("Brak miejsca na OTA");return;}
  mbedtls_sha256_context hash;mbedtls_sha256_init(&hash);mbedtls_sha256_starts(&hash,0);
  auto *stream=http.getStreamPtr();uint8_t buffer[1024],digest[32];size_t total=0;bool good=true;
  while(total<size) {
    size_t wanted=min(sizeof(buffer),size_t(size)-total);
    size_t count=readTlsExact(stream,buffer,wanted,15000);
    if(!count || (total==0 && !validFirmwareHeader(buffer,count))) {good=false;break;}
    mbedtls_sha256_update(&hash,buffer,count);
    if(Update.write(buffer,count)!=count){good=false;break;}
    total+=count;
    if(total%65536==0) {char progress[48];snprintf(progress,sizeof(progress),"Pobieranie firmware: %u%%",unsigned(total*100/size));setOtaMessage(progress);}
    vTaskDelay(1);
  }
  mbedtls_sha256_finish(&hash,digest);mbedtls_sha256_free(&hash);
  char actual[65];for(int i=0;i<32;i++)sprintf(actual+i*2,"%02x",digest[i]);
  http.end();
  if(!good || total!=size || expected!=String(actual)) {char message[96];snprintf(message,sizeof(message),"Blad OTA: ok=%d bajty=%u/%d SHA=%.8s/%.8s err=%u",good,unsigned(total),size,actual,expected.c_str(),unsigned(Update.getError()));Update.abort();setOtaMessage(message);return;}
  if(!Update.end()) {setOtaMessage("Weryfikacja OTA nie powiodla sie");return;}
  setOtaMessage("Aktualizacja gotowa. Restart...");
  rebootAt.store(millis()+1200);
}
static void remoteWorker(void *) {
  WiFiClientSecure client;client.setCACert(REMOTE_CA);client.setHandshakeTimeout(5);
  HTTPClient http;
  const String url="https://" REMOTE_HOST ":"+String(REMOTE_PORT)+"/api/device/stream";
  for(;;) {
    if(otaRequested.exchange(false)) {
      http.end();
      downloadFirmware();
      if(!rebootAt.load())otaBusy.store(false);
    }
    if(otaBusy.load() || !remoteWanted.load() || WiFi.status()!=WL_CONNECTED) {
      vTaskDelay(pdMS_TO_TICKS(100));continue;
    }
    if(time(nullptr)<1700000000) {setRemoteMessage("Czekam na czas NTP dla HTTPS");vTaskDelay(pdMS_TO_TICKS(500));continue;}
    if(!http.begin(client,url)) {setRemoteMessage("Blad klienta HTTPS");vTaskDelay(pdMS_TO_TICKS(1000));continue;}
    // HTTP/1.0 makes the response close-delimited: no chunk framing to decode.
    http.useHTTP10(true);http.setConnectTimeout(1500);http.setTimeout(2000);
    http.addHeader("Authorization","Bearer " DEVICE_TOKEN);
    http.addHeader("X-Device-ID",WiFi.macAddress());
    http.addHeader("X-Frames-Received",String(remoteFrames.load()));
    int code=http.GET();
    if(code==200) {
      auto *stream=http.getStreamPtr();
      stream->setTimeout(2000);
      uint8_t packet[1204];
      while(remoteWanted.load() && !otaBusy.load() && WiFi.status()==WL_CONNECTED) {
        size_t count=readTlsExact(stream,packet,sizeof(packet),2000,true);
        if(count!=sizeof(packet))break;
        if(!remoteWanted.load())break;
        portENTER_CRITICAL(&remoteMux);
        memcpy(remotePixels,packet+4,1200);++remoteGeneration;
        portEXIT_CRITICAL(&remoteMux);
        remoteFrames.fetch_add(1);remoteLastMs.store(millis());
        setRemoteMessage("Odbieram strumien z serwera");
        vTaskDelay(1);
      }
    }
    http.end();
    if(remoteWanted.load())setRemoteMessage(code==401?"Serwer odrzucil klucz urzadzenia":"Brak danych; ponawiam polaczenie");
    vTaskDelay(pdMS_TO_TICKS(300));
  }
}
static bool consumeRemoteFrame() {
  static uint32_t consumed=0;
  bool fresh=false;
  portENTER_CRITICAL(&remoteMux);
  if(consumed!=remoteGeneration) {memcpy(preview,remotePixels,sizeof(preview));consumed=remoteGeneration;fresh=true;}
  portEXIT_CRITICAL(&remoteMux);
  if(!fresh)return false;
  // Remote RGB already includes scene brightness. Keep physical layout on the device.
  for(int y=0;y<20;y++)for(int x=0;x<20;x++){
    int led=cfg.layout=="columns"?x*20+y:cfg.layout=="columns-serpentine"?x*20+(x%2?19-y:y):
      cfg.layout=="rows"?y*20+x:y*20+(y%2?19-x:x);
    for(int c=0;c<3;c++){
      int channel=cfg.order[c]=='R'?0:cfg.order[c]=='G'?1:2;
      pixels[led*3+c]=preview[(y*20+x)*3+channel];
    }
  }
  markPending();return true;
}
static bool otaUploadOK=false,otaUploadAuthenticated=false;
static bool otaAuthorized() {
  String origin=web.header("Origin");
  return (!origin.length() || origin=="http://"+web.hostHeader()) && web.authenticate(OTA_USER,OTA_PASSWORD);
}
static void setupRemote() {
  const char *headers[]={"Origin"};web.collectHeaders(headers,1);
  configTime(0,0,"pool.ntp.org","time.google.com","time.cloudflare.com");
  publishRemoteSettings();
  web.on("/api/remote",HTTP_GET,[]{web.send(200,"application/json",remoteStatus());});
  web.on("/api/update",HTTP_POST,[]{
    if(!otaAuthorized()){web.requestAuthentication();return;}
    if(otaBusy.exchange(true)){web.send(409,"application/json","{\"error\":\"Aktualizacja trwa\"}");return;}
    setOtaMessage("Oczekiwanie na pobranie");otaRequested.store(true);
    web.send(202,"application/json","{\"ok\":true}");
  });
  web.on("/update",HTTP_GET,[]{
    if(!otaAuthorized()){web.requestAuthentication();return;}
    web.send(200,"text/html; charset=utf-8",
      "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>Aktualizacja ESP32</title>"
      "<style>body{font:18px system-ui;max-width:600px;margin:40px auto;padding:20px;background:#101621;color:white}button,input{font:inherit;padding:16px;margin:12px 0;max-width:100%}</style>"
      "<h1>Aktualizacja ESP32</h1><p>Wybierz plik aplikacji led400.bin. Nie odlaczaj zasilania podczas aktualizacji.</p>"
      "<form method='post' action='/update' enctype='multipart/form-data'><input type='file' name='firmware' accept='.bin' required><button>Wgraj firmware</button></form>"
      "<button onclick=\"fetch('/api/update',{method:'POST'}).then(async r=>{if(!r.ok)throw Error(await r.text());document.getElementById('result').textContent='Pobieranie z serwera. Po restarcie otworz panel ponownie.'}).catch(e=>alert(e))\">Aktualizuj z serwera</button>"
      "<p id='result'></p><p><a style='color:#6ce5b5' href='/'>Wroc do panelu</a></p>");
  });
  web.on("/update",HTTP_POST,[]{
    if(!otaAuthorized()){web.requestAuthentication();return;}
    web.send(otaUploadOK?200:400,"text/plain; charset=utf-8",otaUploadOK?"Zapisano firmware. Restart...":"Aktualizacja nieudana. Sprawdz plik i status w panelu.");
    if(otaUploadOK)rebootAt.store(millis()+1200);
  },[]{
    HTTPUpload &upload=web.upload();
    if(upload.status==UPLOAD_FILE_START) {
      otaUploadOK=false;
      otaUploadAuthenticated=otaAuthorized();
      if(!otaUploadAuthenticated)return;
      if(otaBusy.exchange(true)){otaUploadAuthenticated=false;return;}
      setOtaMessage("Wgrywanie pliku...");
      otaUploadOK=Update.begin(UPDATE_SIZE_UNKNOWN,U_FLASH);
    } else if(upload.status==UPLOAD_FILE_WRITE && otaUploadAuthenticated && otaUploadOK) {
      if((upload.totalSize==0 && !validFirmwareHeader(upload.buf,upload.currentSize)) ||
          Update.write(upload.buf,upload.currentSize)!=upload.currentSize) {
        Update.abort();otaUploadOK=false;
      }
    } else if(upload.status==UPLOAD_FILE_END && otaUploadAuthenticated) {
      otaUploadOK=otaUploadOK && Update.end(true);
      if(!otaUploadOK){Update.abort();otaBusy.store(false);setOtaMessage("Niepoprawny plik firmware");}
      else setOtaMessage("Firmware zapisany. Restart...");
    } else if(upload.status==UPLOAD_FILE_ABORTED && otaUploadAuthenticated) {
      Update.abort();otaUploadOK=false;otaBusy.store(false);setOtaMessage("Wgrywanie przerwane");
    }
  });
  xTaskCreatePinnedToCore(remoteWorker,"led-remote",16384,nullptr,1,nullptr,0);
}
