const $=id=>document.getElementById(id);
let libraryFilter='all',libraryGeneration=0,thumbnails=[],sceneQueue=Promise.resolve();
let previewBrightness=24,scene={},shapes=[],mode='text',direction='left',editId=null,frames=[Array(1200).fill(0)],frameIndex=0,eraser=false,history=[],drawing=false,lastCell=null,toastTimer;
const colors=['#ffffff','#ff3355','#ff9900','#ffee00','#35e878','#00ccff','#7855ff','#ff55cc'];
function toast(message){$('toast').textContent=message;$('toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').style.display='none',3500);}
async function api(path,options={}){const r=await fetch(path,{...options,signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json',...(options.headers||{})}});let data;try{data=await r.json()}catch{throw Error('Niepoprawna odpowiedź serwera')}if(!r.ok)throw Error(data.error||'Błąd '+r.status);return data;}
function tab(name){document.querySelectorAll('.tab').forEach(e=>e.hidden=e.id!==name);document.querySelectorAll('nav button').forEach(e=>e.classList.toggle('active',e.dataset.tab===name));if(name==='draw')drawEditor();}
document.querySelectorAll('nav button').forEach(e=>e.onclick=()=>tab(e.dataset.tab));
function updateControls(){
 document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('selected',b.dataset.mode===mode));
 document.querySelectorAll('[data-dir]').forEach(b=>b.classList.toggle('selected',b.dataset.dir===direction));
 $('animationOptions').hidden=mode!=='custom';
 $('textOptions').hidden=mode!=='text';$('counterOptions').hidden=mode!=='counter';
 $('speedOut').value=$('speed').value;$('brightnessOut').value=Math.round($('brightness').value/255*100)+'%';
}
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;updateControls()});
document.querySelectorAll('[data-dir]').forEach(b=>b.onclick=()=>{direction=b.dataset.dir;updateControls()});
for(const id of ['speed','brightness'])$(id).oninput=updateControls;
function applyConfig(c){scene=c;mode=c.mode;direction=c.direction;for(const k of ['text','start','color','speed','brightness','scale','blinkMs'])$(k).value=c[k];$('blink').checked=c.blink;$('invert').checked=c.invert;$('animate').checked=c.animate!==false;updateControls();}
function readScene(){const c={...scene,mode,direction,enabled:true};for(const k of ['text','color'])c[k]=$(k).value;for(const k of ['start','speed','brightness','scale','blinkMs'])c[k]=Number($(k).value);for(const k of ['blink','invert','animate'])c[k]=$(k).checked;return c;}
function updatePlaying(state){const c=state.scene,s=state.shapes.find(s=>s.id===c.shapeId);$('playing').textContent=!c.enabled?'Wyłączone ręcznie':state.schedule&& !state.schedule.active?'Poza godzinami świecenia · czeka na '+state.schedule.on:c.mode==='custom'?(s?s.name:'Wybrany kształt')+(s&&s.frames>1?(c.animate?' · odtwarzanie':' · pierwsza klatka'):' · obraz stały'):c.mode==='text'?c.text:'Animacja: '+c.mode;}
function changeScene(path,data){sceneQueue=sceneQueue.catch(()=>{}).then(async()=>{const state=await api(path,{method:'POST',body:JSON.stringify(data)});applyConfig(state.scene);updatePlaying(state);toast(!state.scene.enabled?'Lampki zgaszone':state.schedule&&!state.schedule.active?'Zapisano obraz · czeka na godzinę włączenia':'Wyświetlanie uruchomione');return state;});return sceneQueue;}
function setScene(c){return changeScene('/api/scene',c);}
function playShape(id){return changeScene('/api/shapes/'+encodeURIComponent(id)+'/play',{});}

function showSchedule(config,fill=false){
 if(!config)return;
 if(fill){$('scheduleEnabled').checked=config.enabled;$('scheduleOn').value=config.on;$('scheduleOff').value=config.off;$('scheduleTimezone').value=config.timezone;}
 const time=config.localTime.slice(11,19);
 $('scheduleStatus').textContent=(config.enabled?'Codziennie '+config.on+'–'+config.off+' · '+(config.active?'godziny świecenia':'lampki czekają na włączenie'):'Harmonogram wyłączony')+' · zegar: '+time+' ('+config.timezone+')';
}
$('scheduleForm').onsubmit=async e=>{
 e.preventDefault();const button=$('saveSchedule');button.disabled=true;
 try{const s=await api('/api/schedule',{method:'POST',body:JSON.stringify({enabled:$('scheduleEnabled').checked,on:$('scheduleOn').value,off:$('scheduleOff').value,timezone:$('scheduleTimezone').value.trim()})});showSchedule(s.schedule,true);updatePlaying(s);toast('Harmonogram zapisany');}
 catch(e){toast(e.message)}finally{button.disabled=false}
};

$('apply').onclick=()=>setScene(readScene()).catch(e=>toast(e.message));
$('off').onclick=()=>setScene({enabled:false}).catch(e=>toast(e.message));
function drawPixels(canvas,pixels,grid=false,gain=1){
 const ctx=canvas.getContext('2d'),scale=canvas.width/20;
 ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,canvas.height);
 for(let i=0;i<400;i++){ctx.fillStyle='rgb('+pixels.slice(i*3,i*3+3).map(v=>Math.min(255,Math.round(v*gain))).join(',')+')';ctx.fillRect((i%20)*scale,Math.floor(i/20)*scale,scale,scale);}
 if(grid){ctx.strokeStyle='#334355';ctx.lineWidth=.6;for(let i=0;i<=20;i++){ctx.beginPath();ctx.moveTo(i*scale,0);ctx.lineTo(i*scale,canvas.height);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i*scale);ctx.lineTo(canvas.width,i*scale);ctx.stroke();}}
}
function drawEditor(){drawPixels($('editor'),frames[frameIndex],true);$('frameLabel').textContent='Klatka '+(frameIndex+1)+' / '+frames.length;}
function remember(){history.push({frames:frames.map(f=>f.slice()),index:frameIndex});if(history.length>20)history.shift();}
function paint(x,y){const col=eraser?[0,0,0]:$('paintColor').value.match(/[a-f\d]{2}/gi).map(x=>parseInt(x,16));const i=(y*20+x)*3;frames[frameIndex].splice(i,3,...col);}
function point(e){const r=$('editor').getBoundingClientRect();return [Math.max(0,Math.min(19,Math.floor((e.clientX-r.left)/r.width*20))),Math.max(0,Math.min(19,Math.floor((e.clientY-r.top)/r.height*20)))];}
function stroke(e){const cell=point(e);if(lastCell){let [x,y]=lastCell;const [tx,ty]=cell,dx=Math.abs(tx-x),dy=-Math.abs(ty-y),sx=x<tx?1:-1,sy=y<ty?1:-1;let err=dx+dy;while(true){paint(x,y);if(x===tx&&y===ty)break;let v=2*err;if(v>=dy){err+=dy;x+=sx}if(v<=dx){err+=dx;y+=sy}}}else paint(...cell);lastCell=cell;drawEditor();}
$('editor').onpointerdown=e=>{e.preventDefault();remember();drawing=true;lastCell=null;$('editor').setPointerCapture(e.pointerId);stroke(e)};
$('editor').onpointermove=e=>{if(drawing)stroke(e)};
for(const name of ['onpointerup','onpointercancel','onlostpointercapture'])$('editor')[name]=()=>{drawing=false;lastCell=null};
$('brush').onclick=()=>{eraser=false;$('brush').classList.add('selected');$('eraser').classList.remove('selected')};
$('eraser').onclick=()=>{eraser=true;$('eraser').classList.add('selected');$('brush').classList.remove('selected')};
$('undo').onclick=()=>{const h=history.pop();if(h){frames=h.frames;frameIndex=h.index;drawEditor()}};
for(const [id,input] of [['paintSwatches','paintColor'],['effectSwatches','color']])for(const color of colors){const b=document.createElement('button');b.style.background=color;b.setAttribute('aria-label',color);b.onclick=()=>{$(input).value=color;if(input==='paintColor')$('brush').click()};$(id).append(b);}
function stamp(kind){remember();frames[frameIndex]=Array(1200).fill(0);const old=eraser;eraser=false;
 for(let y=0;y<20;y++)for(let x=0;x<20;x++){let on=false;
 if(kind==='heart'){const a=(x-9.5)/8,b=(10-y)/8;on=(a*a+b*b-1)**3-a*a*b*b*b<=0;}
 if(kind==='circle')on=Math.abs(Math.hypot(x-9.5,y-9.5)-7)<.8;
 if(kind==='smile')on=Math.abs(Math.hypot(x-9.5,y-9.5)-8)<.7||((x===6||x===13)&&y>=6&&y<=8)||(y>=11&&y<=15&&Math.abs(Math.hypot(x-9.5,y-9)-6)<.65);
 if(kind==='arrow')on=(y>=8&&y<=11&&x>=2&&x<=15)||(x>=10&&x<=17&&Math.abs(y-9.5)<=17-x);
 if(kind==='star'){const a=Math.atan2(y-9.5,x-9.5)+Math.PI/2,r=Math.hypot(x-9.5,y-9.5);on=r<5.6+2.8*Math.cos(a*5);}
 if(on)paint(x,y);}
 eraser=old;drawEditor();
}
document.querySelectorAll('[data-stamp]').forEach(b=>b.onclick=()=>stamp(b.dataset.stamp));
$('clear').onclick=()=>{remember();frames[frameIndex]=Array(1200).fill(0);drawEditor()};
$('prevFrame').onclick=()=>{frameIndex=(frameIndex+frames.length-1)%frames.length;drawEditor()};
$('nextFrame').onclick=()=>{frameIndex=(frameIndex+1)%frames.length;drawEditor()};
function add(copy){if(frames.length>=32)return toast('Maksymalnie 32 klatki');remember();frames.splice(frameIndex+1,0,copy?frames[frameIndex].slice():Array(1200).fill(0));frameIndex++;drawEditor();}
$('addFrame').onclick=()=>add(false);$('copyFrame').onclick=()=>add(true);
$('removeFrame').onclick=()=>{if(frames.length===1)return toast('Zostaw przynajmniej jedną klatkę');remember();frames.splice(frameIndex,1);frameIndex=Math.min(frameIndex,frames.length-1);drawEditor()};
function newShape(){editId=null;frames=[Array(1200).fill(0)];frameIndex=0;history=[];$('shapeName').value='';$('shapeSlideshow').checked=false;drawEditor();tab('draw');}
$('newShape').onclick=()=>{if(confirm('Rozpocząć nowy rysunek? Niezapisane zmiany zostaną utracone.'))newShape()};
$('goDraw').onclick=newShape;
$('saveShape').onclick=async()=>{const button=$('saveShape');button.disabled=true;try{
 const data={name:$('shapeName').value,frames,durationMs:Number($('durationMs').value),kind:$('shapeSlideshow').checked?'slideshow':frames.length>1?'animation':'image'};
 const s=await api('/api/shapes'+(editId?'/'+editId:''),{method:editId?'PUT':'POST',body:JSON.stringify(data)});editId=s.id;
 await library();tab('library');toast('Zapisano kształt');}catch(e){toast(e.message)}finally{button.disabled=false}};
async function library(){
 const generation=++libraryGeneration;const state=await api('/api/state');if(generation!==libraryGeneration)return;
 shapes=state.shapes;thumbnails=[];const box=$('shapes'),shows=$('slideshows');box.replaceChildren();shows.replaceChildren();
 if(!shapes.length){const p=document.createElement('p');p.className='hint';p.textContent='Tu pojawią się Twoje rysunki. Zacznij od serca lub narysuj coś palcem.';box.append(p);return;}
 for(const meta of shapes.filter(s=>libraryFilter==='all'||(libraryFilter==='christmas'?s.name.startsWith('Święta · '):s.kind==='animation'))){const s=await api('/api/shapes/'+meta.id);if(generation!==libraryGeneration)return;
 const card=document.createElement('article');card.className='shape';card.dataset.shapeId=s.id;card.dataset.kind=s.kind;
 const canvas=document.createElement('canvas');canvas.width=canvas.height=20;drawPixels(canvas,s.frames[0]);
 if(s.kind==='animation')thumbnails.push({canvas,frames:s.frames,duration:s.durationMs});
 const title=document.createElement('h3');title.textContent=s.name;const small=document.createElement('small');small.textContent=(s.kind==='slideshow'?'POKAZ RÓŻNYCH OBRAZKÓW':s.kind==='animation'?'ANIMACJA · ten sam motyw':'OBRAZ STAŁY')+(s.frames.length>1?' · '+s.frames.length+' kl.':'');
 const actions=document.createElement('div');actions.className='actions';
 for(const [label,aria,fn] of [
 [s.kind==='slideshow'?'▶ Pokaz':'▶','Wyświetl '+s.name,async()=>{await playShape(s.id);tab('play')}],
 ['✎','Edytuj '+s.name,async()=>{editId=s.id;frames=s.frames.map(f=>f.slice());frameIndex=0;history=[];$('shapeName').value=s.name;$('durationMs').value=s.durationMs;$('shapeSlideshow').checked=s.kind==='slideshow';tab('draw')}],
 ['×','Usuń '+s.name,async()=>{if(confirm('Usunąć „'+s.name+'”?')){await api('/api/shapes/'+s.id,{method:'DELETE'});await library()}}]
 ]){const b=document.createElement('button');b.textContent=label;b.setAttribute('aria-label',aria);b.onclick=()=>fn().catch(e=>toast(e.message));actions.append(b);}
 card.append(canvas,title,small,actions);(s.kind==='slideshow'?shows:box).append(card);
 }
}
for(const [id,filter] of [['allShapes','all'],['christmasShapes','christmas'],['animatedShapes','animated']])$(id).onclick=()=>{
 libraryFilter=filter;$('allShapes').classList.toggle('selected',filter==='all');$('christmasShapes').classList.toggle('selected',filter==='christmas');$('animatedShapes').classList.toggle('selected',filter==='animated');
 library().catch(e=>toast(e.message));
};
setInterval(()=>{if(document.hidden||$('library').hidden)return;const t=performance.now();for(const item of thumbnails){if(item.canvas.isConnected)drawPixels(item.canvas,item.frames[Math.floor(t/item.duration)%item.frames.length]);}},100);
async function preview(){try{const r=await fetch('/api/preview',{signal:AbortSignal.timeout(4000)});if(!r.ok)throw Error();const b=new Uint8Array(await r.arrayBuffer());if(b.length===1200)drawPixels($('preview'),Array.from(b),false,previewBrightness>0?255/previewBrightness:1);}catch{}setTimeout(preview,150)}
async function status(){try{const s=await api('/api/state');previewBrightness=s.scene.brightness;const online=s.devices.filter(d=>d.online);$('device').textContent=online.length?'● ESP32 online':'○ ESP32 offline';$('device').classList.toggle('online',online.length>0);$('deviceDetails').textContent=s.devices.map(d=>d.id+': wysłano '+(d.framesSent||0)+' klatek').join(' · ')||'Czekam na ESP32. Wybierz tryb serwera na urządzeniu.';updatePlaying(s);showSchedule(s.schedule);}catch{$('device').textContent='Brak połączenia'}setTimeout(status,2000)}
(async()=>{try{const s=await api('/api/state');applyConfig(s.scene);showSchedule(s.schedule,true);await library();drawEditor();preview();status()}catch(e){toast(e.message)}})();
