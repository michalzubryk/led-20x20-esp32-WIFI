import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schedule import DEFAULT_SCHEDULE,validate_schedule,schedule_status
from app import Studio
from render import DEFAULT
import test_app


def instant(value):
    return datetime.fromisoformat(value)


class ScheduleTest(unittest.TestCase):
    def test_daily_boundaries_and_disabled(self):
        config=validate_schedule(dict(enabled=True,on="16:00",off="23:00",timezone="UTC"))
        for clock,expected in [("15:59:59",False),("16:00:00",True),("22:59:59",True),("23:00:00",False)]:
            self.assertEqual(schedule_status(config,instant('2026-11-08T'+clock+'+00:00'))['active'],expected)
        config['enabled']=False
        self.assertTrue(schedule_status(config,instant('2026-11-08T04:00:00+00:00'))['active'])

    def test_midnight(self):
        config=validate_schedule(dict(enabled=True,on="18:00",off="01:00",timezone="UTC"))
        for clock,expected in [('17:59',False),('18:00',True),('23:59',True),('00:00',True),('00:59',True),('01:00',False)]:
            self.assertEqual(schedule_status(config,instant('2026-11-08T'+clock+':00+00:00'))['active'],expected)

    def test_dst_wall_clock(self):
        config=validate_schedule(dict(enabled=True,on="16:00",off="23:00"))
        self.assertTrue(schedule_status(config,instant('2026-07-08T14:00:00+00:00'))['active'])
        self.assertFalse(schedule_status(config,instant('2026-11-08T14:00:00+00:00'))['active'])
        # Both occurrences of the repeated autumn hour are inside the window.
        config.update(on='02:15',off='02:45')
        for clock in ('00:30','01:30'):
            self.assertTrue(schedule_status(config,instant('2026-10-25T'+clock+':00+00:00'))['active'])
        # Spring jumps directly from before the window to its end.
        config.update(on='02:00',off='03:00')
        for clock in ('00:59','01:00'):
            self.assertFalse(schedule_status(config,instant('2026-03-29T'+clock+':00+00:00'))['active'])

    def test_validation(self):
        for data in [[],{'enabled':1},{'on':'24:00'},{'off':'2:00'},{'on':'12:60'},
                     {'timezone':'invalid/zone'},{'timezone':'/etc/passwd'},{'timezone':False},
                     {'on':'16:00','off':'16:00'},{'unknown':True}]:
            with self.subTest(data=data),self.assertRaises(ValueError):validate_schedule(data)

    def test_migration_render_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            original={**DEFAULT,'mode':'pulse','direction':'none','color':'#ffffff'}
            Path(folder,'studio.json').write_text(json.dumps(dict(scene=original,shapes={})))
            studio=Studio(folder)
            self.assertEqual(studio.schedule,DEFAULT_SCHEDULE)
            studio.save(schedule=validate_schedule(dict(enabled=True,on='18:00',off='01:00',timezone='UTC')))
            restored=Studio(folder)
            on=instant('2026-11-08T20:00:00+00:00');off=instant('2026-11-08T12:00:00+00:00')
            self.assertEqual(restored.render_frame(0,off),bytes(1200))
            self.assertEqual(restored.render_frame(0,on),bytes([24]*1200))
            self.assertEqual(restored.scene,original)
            restored.scene['enabled']=False
            self.assertEqual(restored.render_frame(0,on),bytes(1200))


# Reuse setup/teardown only; avoid executing inherited tests twice.
class ScheduleAPITest(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_app.AppTest.asyncSetUp
    asyncTearDown=test_app.AppTest.asyncTearDown

    async def test_auth_save_error_atomicity(self):
        self.assertEqual((await self.client.post('/api/schedule',json={})).status,401)
        data=dict(enabled=True,on='18:00',off='01:00',timezone='Europe/Warsaw')
        r=await self.client.post('/api/schedule',headers=self.auth,json=data)
        self.assertEqual(r.status,200)
        self.assertEqual(Studio(self.tmp.name).schedule,data)
        original=self.app['studio'].schedule.copy()
        for invalid in ({'on':'25:00'},{'timezone':'bad/zone'}):
            r=await self.client.post('/api/schedule',headers=self.auth,json=invalid)
            self.assertEqual(r.status,400)
        with patch('pathlib.Path.write_text',side_effect=OSError('disk')):
            r=await self.client.post('/api/schedule',headers=self.auth,json={'enabled':False})
        self.assertEqual(r.status,507)
        self.assertEqual(self.app['studio'].schedule,original)
        self.assertEqual(Studio(self.tmp.name).schedule,original)
        r=await self.client.post('/api/schedule',headers={**self.auth,'Origin':'https://invalid.example'},json={})
        self.assertEqual(r.status,403)

    async def test_device_and_preview_obey_clock_without_browser(self):
        await self.client.post('/api/scene',headers=self.auth,json={'mode':'pulse','direction':'none','color':'#ffffff'})
        await self.client.post('/api/schedule',headers=self.auth,json={'enabled':True,'on':'18:00','off':'01:00','timezone':'UTC'})
        with patch('schedule.datetime') as clock:
            for value,frame in [('2026-11-08T12:00:00+00:00',bytes(1200)),
                                ('2026-11-08T18:00:00+00:00',bytes([24]*1200)),
                                ('2026-11-09T01:00:00+00:00',bytes(1200))]:
                clock.now.return_value=instant(value)
                await asyncio.sleep(.08)
                for url,headers in [('/api/preview',self.auth),('/api/device/frame',{'Authorization':'Bearer device-secret'})]:
                    r=await self.client.get(url,headers=headers)
                    self.assertEqual(await r.read(),frame)
        self.assertTrue(self.app['studio'].scene['enabled'])
