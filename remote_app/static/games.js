/* Games share the authenticated studio API and existing 20x20 preview stream. */
(()=>{
 let game={active:false},busy=false,version=0,held=null,paddleDragging=false,pendingPaddle=null,pauseRequested=false,pendingBrightness=null;
 const visible=()=>!$('games').hidden&&!document.hidden;
 const names={arkanoid:'Arkanoid',tetris:'Tetris'};
 const reasons={manual:'Pauza',idle:'Pauza · brak sterowania',schedule:'Pauza · poza godzinami świecenia'};
 function show(state){
  game=state.game;
  $('gameControls').hidden=!game.active;
  if(!game.active){$('gameStatus').textContent='Wybierz grę. Po zakończeniu wróci poprzednia animacja.';return;}
  previewBrightness=game.brightness;
  $('arkanoidControls').hidden=game.kind!=='arkanoid';$('tetrisControls').hidden=game.kind!=='tetris';
  const phase=game.paused?reasons[game.paused]:game.phase==='ready'?'Wystrzel piłkę':game.phase==='won'?'Wygrana!':game.phase==='over'?'Koniec gry — wybierz nową grę':'Gramy';
  $('gameStatus').textContent=names[game.kind]+' · '+game.score+' pkt · '+(game.kind==='arkanoid'?game.lives+' życia · '+game.remaining+' cegiełek':game.lines+' linii · poziom '+game.level)+' · '+phase;
  $('pauseGame').textContent=game.paused?'Wznów':'Pauza';
  if(!paddleDragging&&pendingPaddle===null&&game.kind==='arkanoid')$('paddle').value=game.paddle;
  if(document.activeElement!==$('gameBrightness'))$('gameBrightness').value=game.brightness;
  $('gameBrightnessOut').value=Math.round(game.brightness/255*100)+'%';
 }
 function controlsBusy(value){
  busy=value;for(const id of ['startArkanoid','startTetris','pauseGame','stopGame'])$(id).disabled=value;
 }
 async function command(action,value,kind){
  if(busy)return false;
  if(action!=='start'&&!game.active)return false;
  controlsBusy(true);version++;
  const data=action==='start'?{action,kind}:{action,id:game.id};if(value!==undefined)data.value=value;
  try{show(await api('/api/game',{method:'POST',body:JSON.stringify(data)}));if(action==='start')$('gamePreview').focus({preventScroll:true});return true;}
  catch(e){toast(e.message);return false;}
  finally{controlsBusy(false);}
 }
 $('startArkanoid').onclick=()=>command('start',undefined,'arkanoid');
 $('startTetris').onclick=()=>command('start',undefined,'tetris');
 $('pauseGame').onclick=()=>command(game.paused?'resume':'pause');
 $('stopGame').onclick=()=>{release();pendingPaddle=null;command('stop')};
 $('paddle').onpointerdown=()=>paddleDragging=true;
 for(const event of ['pointerup','pointercancel','blur'])$('paddle').addEventListener(event,()=>paddleDragging=false);
 $('paddle').oninput=()=>{pendingPaddle=Number($('paddle').value)};
 $('gameBrightness').oninput=()=>{$('gameBrightnessOut').value=Math.round(Number($('gameBrightness').value)/255*100)+'%'};
 $('gameBrightness').onchange=()=>{pendingBrightness=Number($('gameBrightness').value)};
 function release(){if(held!==null)clearInterval(held);held=null;}
 for(const button of document.querySelectorAll('[data-game-action]')){
  button.onpointerdown=e=>{
   e.preventDefault();release();button.setPointerCapture(e.pointerId);
   command(button.dataset.gameAction);
   if(button.dataset.repeat)held=setInterval(()=>{if(visible())command(button.dataset.gameAction);else release()},150);
  };
  for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,release);
  // Keyboard activation and assistive technology synthesize a click with detail=0.
  button.onclick=e=>{if(e.detail===0)command(button.dataset.gameAction)};
  button.oncontextmenu=e=>e.preventDefault();
 }
 document.addEventListener('keydown',e=>{
  if(!visible()||!game.active||e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,select,textarea,button'))return;
  const actions={ArrowLeft:'left',ArrowRight:'right',ArrowUp:'rotate',ArrowDown:'down',' ':game.kind==='arkanoid'?'launch':'drop',p:game.paused?'resume':'pause',P:game.paused?'resume':'pause'};
  const action=actions[e.key];if(!action)return;
  e.preventDefault();if(e.repeat&&['pause','resume','drop','launch','rotate'].includes(action))return;
  if(game.kind==='arkanoid'&&['rotate','down'].includes(action))return;
  command(action);
 });
 function requestPause(){release();pendingPaddle=null;if(game.active&&!game.paused)pauseRequested=true;}
 window.addEventListener('led-tab',e=>{
  const active=e.detail==='games';document.body.classList.toggle('gaming',active);document.querySelector('.monitor').hidden=active;$('schedulePanel').hidden=active;
  if(!active)requestPause();
 });
 document.addEventListener('visibilitychange',()=>{if(document.hidden)requestPause()});
 window.addEventListener('blur',requestPause);
 setInterval(()=>{
  if(busy)return;
  if(pauseRequested){pauseRequested=false;if(game.active&&!game.paused)command('pause');return;}
  if(visible()&&pendingBrightness!==null){const value=pendingBrightness;pendingBrightness=null;command('brightness',value);return;}
  if(visible()&&pendingPaddle!==null){const position=pendingPaddle;pendingPaddle=null;command('position',position);}
 },60);
 setInterval(()=>{if(visible()&&game.active&&!busy)command('heartbeat')},2000);
 async function poll(){
  if(visible()&&!busy){const current=version;try{const state=await api('/api/game');if(version===current&&!busy)show(state)}catch(e){$('gameStatus').textContent='Brak połączenia — gra zostanie automatycznie wstrzymana';}}
  setTimeout(poll,300);
 }
 poll();
})();
