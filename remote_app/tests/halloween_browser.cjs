// Disposable local studio seeded with both holiday packs only; changes its scene.
const {chromium}=require('playwright');
(async()=>{
 const url=process.env.LED_TEST_URL;
 if(!url||!['127.0.0.1','localhost'].includes(new URL(url).hostname))throw Error('Disposable localhost LED_TEST_URL required');
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
 const p=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,httpCredentials:{username:process.env.BASIC_USER,password:process.env.BASIC_PASSWORD}});
 const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(url);await p.waitForFunction(()=>document.querySelectorAll('#shapes .shape').length>=24);
 await p.locator('[data-tab="library"]').tap();await p.locator('#halloweenShapes').tap();
 await p.waitForFunction(()=>document.querySelectorAll('#shapes .shape').length===10);
 if(await p.locator('#shapes .shape[data-kind="animation"]').count()!==3)throw Error('Expected 3 Halloween animations');
 await p.getByRole('button',{name:'Wyświetl Halloween · Świeczka — migoczący płomień',exact:true}).tap();
 await p.waitForFunction(()=>document.querySelector('#playing').textContent.includes('Świeczka — migoczący płomień'));
 const state=()=>p.evaluate(()=>fetch('/api/state').then(r=>r.json()));
 const pixels=()=>p.evaluate(()=>fetch('/api/preview').then(r=>r.arrayBuffer()).then(b=>JSON.stringify(Array.from(new Uint8Array(b)))));
 const id=(await state()).scene.shapeId,seen=new Set();
 for(let i=0;i<10;i++){await p.waitForTimeout(130);seen.add(await pixels());if((await state()).scene.shapeId!==id)throw Error('Unexpected motif change');}
 if(seen.size<2)throw Error('Candle is not animated');
 await p.locator('#animate').uncheck();await p.locator('#apply').tap();await p.waitForTimeout(200);
 const frozen=await pixels();await p.waitForTimeout(600);if(await pixels()!==frozen)throw Error('Freeze failed');
 await p.locator('[data-tab="library"]').tap();
 if(process.env.SCREENSHOT_PATH)await p.screenshot({path:process.env.SCREENSHOT_PATH,fullPage:true});
 await p.locator('#christmasShapes').tap();await p.waitForFunction(()=>document.querySelectorAll('#shapes .shape').length===14);
 if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('Halloween filter, candle frames, selected motif, freeze, Christmas filter: PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
