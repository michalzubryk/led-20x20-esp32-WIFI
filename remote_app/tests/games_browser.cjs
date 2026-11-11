// Uses a disposable local studio. Mutates games only, then restores the saved scene.
const {chromium}=require('playwright');
(async()=>{
 const base=process.env.LED_TEST_URL;
 if(!base||!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Disposable localhost LED_TEST_URL required');
 const b=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
 const p=await b.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,httpCredentials:{username:process.env.BASIC_USER,password:process.env.BASIC_PASSWORD}});
 const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base);await p.waitForFunction(()=>document.querySelectorAll('#shapes .shape').length>0);
 const state=()=>p.evaluate(()=>fetch('/api/state').then(r=>r.json()));
 const before=await state();
 await p.locator('[data-tab="games"]').tap();await p.locator('#startArkanoid').tap();
 await p.waitForFunction(()=>document.querySelector('#gameStatus').textContent.includes('3 życia'));
 let g=(await state()).game;if(g.kind!=='arkanoid'||g.phase!=='ready')throw Error('Arkanoid start');
 await p.keyboard.press('ArrowRight');await p.waitForTimeout(250);
 if((await state()).game.paddle<=g.paddle)throw Error('Keyboard paddle failed');
 await p.locator('#paddle').evaluate(e=>{e.value='5';e.dispatchEvent(new Event('input',{bubbles:true}))});await p.waitForTimeout(400);
 if((await state()).game.paddle!==5)throw Error('Touch paddle position failed');
 await p.locator('[data-game-action="launch"]').tap();await p.waitForTimeout(200);
 if((await state()).game.phase!=='playing')throw Error('Launch failed');
 await p.locator('#pauseGame').tap();await p.waitForFunction(()=>document.querySelector('#pauseGame').textContent==='Wznów');
 if((await state()).game.paused!=='manual')throw Error('Pause failed');
 await p.evaluate(()=>window.scrollTo(0,0));if(process.env.SCREENSHOT_DIR)await p.screenshot({path:process.env.SCREENSHOT_DIR+'/arkanoid.png',fullPage:true});
 await p.locator('#pauseGame').tap();await p.waitForFunction(()=>document.querySelector('#pauseGame').textContent==='Pauza');
 // Start another game; old commands must not apply to it.
 const old=(await state()).game.id;
 await p.locator('#startTetris').tap();await p.waitForFunction(()=>document.querySelector('#gameStatus').textContent.includes('Tetris'));
 const current=(await state()).game.id;if(current===old)throw Error('Round ID reused');
 const stale=await p.evaluate(id=>fetch('/api/game',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',id})}).then(r=>r.status),old);
 if(stale!==409)throw Error('Stale controller accepted');
 await p.locator('[data-game-action="rotate"]').tap();await p.waitForTimeout(200);
 await p.locator('[data-game-action="drop"]').tap();await p.waitForTimeout(300);
 if((await state()).game.score<=0)throw Error('Hard drop failed');
 await p.evaluate(()=>window.scrollTo(0,0));if(process.env.SCREENSHOT_DIR)await p.screenshot({path:process.env.SCREENSHOT_DIR+'/tetris.png',fullPage:true});
 await p.locator('[data-tab="play"]').tap();await p.waitForTimeout(400);
 if((await state()).game.paused!=='manual')throw Error('Leaving tab failed to pause');
 await p.locator('[data-tab="games"]').tap();await p.locator('#stopGame').tap();
 await p.waitForFunction(()=>document.querySelector('#gameControls').hidden);
 const after=await state();if(after.game.active)throw Error('Stop failed');
 if(JSON.stringify(before.scene)!==JSON.stringify(after.scene))throw Error('Saved scene changed');
 if(before.shapes.length!==after.shapes.length)throw Error('Library changed');
 if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('Mobile games: keyboard, touch, launch, pause/resume, drop, stale controls, exit and scene restore PASS');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
