// Run only against a disposable local demo; this test changes its schedule.
// npm install --no-save playwright; npx playwright install chromium
// LED_TEST_URL=http://127.0.0.1:8080 BASIC_USER=... BASIC_PASSWORD=... node tests/schedule_browser.cjs
const {chromium}=require('playwright');
(async()=>{
 const base=process.env.LED_TEST_URL;
 if(!base||!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('A disposable localhost LED_TEST_URL is required');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,httpCredentials:{username:process.env.BASIC_USER,password:process.env.BASIC_PASSWORD}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#scheduleStatus').textContent.includes('zegar:'));
 await page.locator('#schedulePanel summary').tap();
 await page.locator('#scheduleEnabled').check();
 const minute=Math.floor(Date.now()/60000)%1440;
 const hhmm=m=>{m=(m+1440)%1440;return String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0')};
 await page.locator('#scheduleTimezone').fill('UTC');
 await page.locator('#scheduleOn').fill(hhmm(minute+120));await page.locator('#scheduleOff').fill(hhmm(minute+180));
 // Background polling must not discard unfinished edits.
 await page.waitForTimeout(2200);
 if(await page.locator('#scheduleOn').inputValue()!==hhmm(minute+120))throw Error('Draft overwritten');
 await page.locator('#saveSchedule').tap();
 await page.waitForFunction(()=>document.querySelector('#toast').textContent==='Harmonogram zapisany');
 await page.waitForTimeout(200);
 const pixels=()=>page.evaluate(()=>fetch('/api/preview').then(r=>r.arrayBuffer()).then(b=>Array.from(new Uint8Array(b))));
 if((await pixels()).some(Boolean))throw Error('Expected black frame outside window');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#scheduleEnabled').checked);
 if(await page.locator('#scheduleOn').inputValue()!==hhmm(minute+120))throw Error('Schedule not restored');
 await page.locator('#schedulePanel summary').tap();
 await page.locator('#scheduleOn').fill(hhmm(minute-60));await page.locator('#scheduleOff').fill(hhmm(minute+60));
 await page.locator('#saveSchedule').tap();await page.waitForTimeout(400);
 if(!(await pixels()).some(Boolean))throw Error('Expected active demo scene inside window');
 await page.locator('#scheduleOn').fill('16:00');await page.locator('#scheduleOff').fill('16:00');await page.locator('#saveSchedule').tap();
 await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('muszą być różne'));
 await page.locator('#scheduleOff').fill('23:00');await page.locator('#scheduleTimezone').fill('Europe/Warsaw');
 await page.locator('#scheduleEnabled').uncheck();await page.locator('#saveSchedule').tap();await page.waitForTimeout(400);
 if(process.env.SCREENSHOT_PATH)await page.locator('#schedulePanel').screenshot({path:process.env.SCREENSHOT_PATH});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('Mobile schedule: save/reload, draft retention, black/active frames, validation and layout PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
