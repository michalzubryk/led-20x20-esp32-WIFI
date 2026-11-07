static const char PAGE[] PROGMEM = R"HTMLPAGE(<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LED Studio · ESP32</title>
<style>
:root{color-scheme:dark;font-family:system-ui;background:#101521;color:#edf3ff}*{box-sizing:border-box}body{max-width:1040px;margin:auto;padding:24px}h1{margin-bottom:8px}p,small{color:#b0bfd4;line-height:1.6}main{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px}section{background:#192132;border:1px solid #32405a;border-radius:18px;padding:22px}label{display:block;margin:15px 0 7px}select,input,button{font:inherit;color:inherit;background:#101827;border:1px solid #465978;border-radius:8px;padding:9px}select,input:not([type=checkbox]):not([type=color]){width:100%}input[type=color]{height:42px;width:80px;padding:4px}input[type=range]{accent-color:#6ce5b5}button{cursor:pointer;margin:6px 6px 0 0}.primary{background:#6ce5b5;color:#092b1d;font-weight:700}.row{display:flex;gap:12px}.row>*{flex:1}canvas{width:100%;aspect-ratio:1;background:black;image-rendering:pixelated;border-radius:8px}#message{color:#6ce5b5;min-height:25px}details{margin-top:20px}summary{cursor:pointer}@media(max-width:700px){main{grid-template-columns:1fr}body{padding:15px}}
</style>
<h1>LED Studio <small>20 × 20 · ESP32</small></h1>
<p>Generator działa w lampkach. Komputer i karta przeglądarki mogą być wyłączone.</p>
<main><section><form id="form">
<label for="source">Skąd ma pochodzić obraz?</label>
<select id="source"><option value="local">Generator w ESP32</option><option value="server">Serwer zdalny</option><option value="stream">Aplikacja USB / DDP w sieci lokalnej</option></select>
<p id="remoteInfo">Łączenie ze statusem urządzenia…</p>
<a style="color:#6ce5b5" id="serverLink" href="#" target="_blank" rel="noopener">Otwórz pilot i edytor na serwerze ↗</a>
<p><small>W trybie serwera obraz pochodzi ze zdalnej aplikacji. Po 3 s bez danych wraca poniższa animacja lokalna; ESP32 ponawia połączenie.</small></p>
<label for="mode">Animacja lokalna / awaryjna</label><select id="mode"><option value="text">Tekst lub liczba</option><option value="counter">Licznik +1 co sekundę</option><option value="rainbow">Tęcza</option><option value="bars">Wędrujące pasy</option><option value="pulse">Pulsujący kolor</option><option value="bounce">Odbijający się kwadrat</option></select>
<div id="textBox"><label for="text">Tekst / liczba</label><input id="text" maxlength="100" value="HELLO 123"></div>
<div id="counterBox" hidden><label for="start">Licz od</label><input id="start" type="number" min="0" max="999999" value="0"></div>
<div class="row"><div><label for="direction">Ruch</label><select id="direction"><option value="left">← W lewo</option><option value="right">W prawo →</option><option value="up">↑ W górę</option><option value="down">↓ W dół</option><option value="none">Bez ruchu</option></select></div><div id="scaleBox"><label for="scale">Litery</label><select id="scale"><option value="1">Małe · 10 px</option><option value="2">Duże · 20 px</option></select></div></div>
<small>Przy ruchu góra/dół lub bez ruchu użyj krótkiego tekstu — dłuższy zostanie przycięty.</small>
<label for="speed">Tempo <output id="speedOut"></output></label><input id="speed" type="range" min="1" max="40" value="10">
<div class="row"><div><label for="color">Kolor</label><input id="color" type="color" value="#00ccff"></div><div><label for="brightness">Jasność <output id="brightOut"></output></label><input id="brightness" type="range" min="0" max="255" value="24"></div></div>
<label><input type="checkbox" id="blink"> Miganie</label>
<label for="blinkMs">Czas świecenia / przerwy</label><select id="blinkMs"><option value="150">Szybko · 150 ms</option><option value="500" selected>Średnio · 500 ms</option><option value="1000">Wolno · 1 s</option><option value="2000">Bardzo wolno · 2 s</option></select>
<label><input type="checkbox" id="invert"> Odwróć kolory (negatyw, także tło)</label>
<p><button class="primary" type="submit">▶ Uruchom i zapisz</button><button type="button" id="stop">■ Zgaś</button></p>
</form><div id="message" role="status" aria-live="polite">Łączenie…</div>
<details><summary>Ułożenie lampek</summary><label for="layout">Kolejność</label><select id="layout"><option value="columns">Kolumny</option><option value="columns-serpentine">Kolumny zygzak</option><option value="rows">Wiersze</option><option value="rows-serpentine">Wiersze zygzak</option></select><label for="order">Kolory</label><select id="order"><option>RGB</option><option>GRB</option><option>RBG</option><option>GBR</option><option>BRG</option><option>BGR</option></select></details>
</section><section><canvas id="preview" width="20" height="20" aria-label="Podgląd matrycy"></canvas><p>Zmiany działają na żywo. „Uruchom i zapisz” zachowuje ustawienia po odłączeniu zasilania. „Zgaś” zapisuje wyłączenie.</p><p>Podgląd pokazuje pełne kolory; suwak jasności reguluje lampki. Klatki USB/DDP są przyjmowane tylko w trybie „Aplikacja USB / DDP”. Serwer generuje kolor i jasność; ułożenie lampek ustawiasz tutaj.</p><small id="stats"></small>
<details><summary>Aktualizacja oprogramowania (OTA)</summary>
<p><a style="color:#6ce5b5" href="/update">Otwórz aktualizację ESP32</a></p>
<p>Wgraj plik .bin z telefonu albo wybierz „Aktualizuj z serwera”. Wymagane logowanie. Nie odłączaj zasilania podczas aktualizacji.</p>
<p id="otaStatus"></p></details></section></main>
<script>
const $=id=>document.getElementById(id),keys=['source','mode','text','start','direction','scale','speed','color','brightness','blink','blinkMs','invert','layout','order'];
let queue=Promise.resolve(),timer,ready=false;
function visibility(){$('textBox').hidden=$('mode').value!=='text';$('counterBox').hidden=$('mode').value!=='counter';$('scaleBox').hidden=!['text','counter'].includes($('mode').value);$('speedOut').value=$('speed').value;$('brightOut').value=Math.round($('brightness').value*100/255)+'%';}
function save(extra={}){
 const data={};for(const k of keys)data[k]=['blink','invert'].includes(k)?$(k).checked:$(k).value;
 Object.assign(data,extra);
 queue=queue.catch(()=>{}).then(async()=>{try{const r=await fetch('/api/config',{method:'POST',body:new URLSearchParams(data)});const c=await r.json();if(!r.ok)throw Error(c.error);$('message').textContent=c.enabled?(c.source==='server'?'● Tryb serwera':c.source==='stream'?'● Odbiór USB / DDP':'● Generator działa')+(extra.save?' · zapisano':' · zmiany niezapisane'):'○ Generator wyłączony';}catch(e){$('message').textContent='Błąd: '+e.message;}});
 return queue;
}
for(const k of keys)$(k).addEventListener('input',()=>{visibility();if(!ready)return;clearTimeout(timer);timer=setTimeout(()=>save(),350);});
$('form').onsubmit=e=>{e.preventDefault();clearTimeout(timer);save({enabled:true,save:true});};
$('stop').onclick=()=>{clearTimeout(timer);save({enabled:false,save:true});};
async function poll(){
 try{const r=await fetch('/preview',{signal:AbortSignal.timeout(4000)});if(!r.ok)throw Error();const bytes=new Uint8Array(await r.arrayBuffer());if(bytes.length!==1200)throw Error('preview');const ctx=$('preview').getContext('2d'),im=ctx.createImageData(20,20);for(let i=0;i<400;i++){im.data[i*4]=bytes[i*3];im.data[i*4+1]=bytes[i*3+1];im.data[i*4+2]=bytes[i*3+2];im.data[i*4+3]=255;}ctx.putImageData(im,0,0);}
 catch(e){$('message').textContent='Brak podglądu — sprawdź połączenie z ESP32';}
 setTimeout(poll,250);
}
async function init(){try{const r=await fetch('/api/config');if(!r.ok)throw Error();const c=await r.json();for(const k of keys){if(['blink','invert'].includes(k))$(k).checked=c[k];else $(k).value=c[k];}ready=true;visibility();$('message').textContent=c.enabled?(c.source==='server'?'● Tryb serwera':c.source==='stream'?'● Odbiór USB / DDP':'● Generator działa'):'○ Generator wyłączony';poll();}catch(e){$('message').textContent='Nie udało się połączyć. Odśwież stronę.';}}
async function remotePoll(){
 try{const r=await fetch('/api/remote',{signal:AbortSignal.timeout(4000)});const s=await r.json();
 $('remoteInfo').textContent=s.source==='server'?(s.connected?'● Połączono z serwerem · odebrano '+s.frames+' klatek':s.message+(s.fallback?' · animacja awaryjna':'')):s.source==='stream'?'Czekam na klatki USB / DDP':'Generator działa w ESP32';
 $('serverLink').href=s.host+'/';$('otaStatus').textContent=s.ota;$('stats').textContent=s.version;
 }catch(e){$('remoteInfo').textContent='Nie udało się odczytać statusu ESP32';}
 setTimeout(remotePoll,2000);
}
remotePoll();init();
</script></html>
)HTMLPAGE";
