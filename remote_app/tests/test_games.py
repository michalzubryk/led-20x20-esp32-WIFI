import asyncio
from datetime import datetime
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from games import Breakout,Tetris,GameSession
import test_app
from app import Studio

class EngineTest(unittest.TestCase):
    def test_arkanoid_wall_paddle_lives_and_win(self):
        g=Breakout();g.control('position',17);self.assertEqual(g.x,17)
        g.control('launch');g.x=18.99;g.y=12;g.vx=4;g.vy=-2;g.tick(.02)
        self.assertLess(g.vx,0)
        g.paddle=9;g.x=9;g.y=17.4;g.vy=7;g.vx=0;g.tick(.04)
        self.assertLess(g.vy,0)
        g.x=0;g.y=19.4;g.vy=7;g.vx=0;g.tick(.04)
        self.assertEqual((g.lives,g.phase),(2,'ready'))
        g.control('launch');g.bricks={(0,0)};g.x=1;g.y=3.6;g.vx=0;g.vy=-7;g.tick(.04)
        self.assertEqual(g.phase,'won');self.assertEqual(g.score,10)
        self.assertEqual(len(g.draw()),1200)

    def test_arkanoid_gameover(self):
        g=Breakout();g.lives=1;g.phase='playing';g.x=0;g.y=19.4;g.vx=0;g.vy=7
        g.tick(.05);self.assertEqual(g.phase,'over');self.assertEqual(g.lives,0)
        g.control('launch');g.tick(.1);self.assertEqual(g.phase,'over')

    def test_tetris_drop_clears_line_and_moves_remaining_rows(self):
        g=Tetris(random.Random(3))
        g.board[19]=[1]*10;g.board[18][0]=2
        for x in range(3,7):g.board[19][x]=0
        g.kind=0;g.size=4;g.cells=[(x,1) for x in range(4)];g.x=3;g.y=0
        g.control('drop')
        self.assertEqual(g.lines,1);self.assertGreaterEqual(g.score,100)
        self.assertEqual(g.board[19][0],2);self.assertFalse(any(g.board[0]))
        self.assertEqual(len(g.draw()),1200)

    def test_rotation_bounds_and_blocked_spawn(self):
        g=Tetris(random.Random(1))
        for _ in range(20):g.control('left')
        for _ in range(4):g.control('rotate');self.assertTrue(g.fits(g.x,g.y,g.cells))
        for _ in range(30):g.control('right')
        self.assertTrue(g.fits(g.x,g.y,g.cells))
        g.board=[[1]*10 for _ in range(20)];g.spawn();self.assertEqual(g.phase,'over')
        old=[row[:] for row in g.board];g.control('drop');g.tick(10);self.assertEqual(g.board,old)

    def test_bag_and_gravity(self):
        g=Tetris(random.Random(1));g.bag=[]
        self.assertEqual(set(g.take() for _ in range(7)),set(range(7)))
        old=g.y
        for _ in range(9):g.tick(.1)
        self.assertEqual(g.y,old+1)

    def test_pause_timeout_schedule_and_input_validation(self):
        clock=[10.];g=GameSession('arkanoid',24,lambda:clock[0])
        g.command('launch');clock[0]=19.;g.tick(clock[0],True)
        self.assertEqual(g.paused,'idle');pos=(g.engine.x,g.engine.y)
        g.command('heartbeat');self.assertEqual(g.paused,'idle')
        clock[0]+=1;g.tick(clock[0],True);self.assertEqual((g.engine.x,g.engine.y),pos)
        g.command('resume');self.assertFalse(g.paused)
        g.tick(clock[0],False);self.assertEqual(g.paused,'schedule')
        with self.assertRaises(ValueError):g.command('resume',allowed=False)
        for v in (True,float('nan'),float('inf'),-1,20,'3'):
            with self.assertRaises(ValueError):g.command('position',v)
        for v in (True,256,-1,.5):
            with self.assertRaises(ValueError):g.command('brightness',v)
        self.assertEqual(len(g.frame()),1200)
        g.command('brightness',0);self.assertEqual(g.frame(),bytes(1200))

class GameAPITest(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_app.AppTest.asyncSetUp
    asyncTearDown=test_app.AppTest.asyncTearDown

    async def command(self,data,headers=None):
        return await self.client.post('/api/game',headers=self.auth if headers is None else headers,json=data)

    async def test_auth_validation_stale_id_and_origin(self):
        self.assertEqual((await self.client.get('/api/game')).status,401)
        self.assertEqual((await self.command({'action':'start','kind':'arkanoid'},{})).status,401)
        self.assertEqual((await self.command({'action':'start','kind':'arkanoid'},{**self.auth,'Origin':'https://evil.invalid'})).status,403)
        for data in ([],{}, {'action':[]},{'action':'start','kind':'bad'},{'action':'start','kind':[]},{'action':'start','kind':'tetris','extra':1}):
            self.assertEqual((await self.command(data)).status,400)
        r=await self.command({'action':'start','kind':'arkanoid'});old=(await r.json())['game']['id']
        r=await self.command({'action':'start','kind':'tetris'});new=(await r.json())['game']['id']
        self.assertNotEqual(old,new)
        self.assertEqual((await self.command({'action':'stop','id':old})).status,409)
        self.assertEqual((await self.command({'action':'rotate','id':new})).status,200)
        self.assertEqual((await self.command({'action':'position','value':True,'id':new})).status,400)

    async def test_output_stop_and_scene_preservation(self):
        await self.client.post('/api/scene',headers=self.auth,json={'mode':'pulse','direction':'none','color':'#ffffff'})
        studio=self.app['studio'];saved=studio.scene.copy();path=studio.path.read_bytes()
        r=await self.command({'action':'start','kind':'tetris'});gid=(await r.json())['game']['id']
        await asyncio.sleep(.06)
        r=await self.client.get('/api/device/frame',headers={'Authorization':'Bearer device-secret'})
        frame=await r.read();self.assertEqual(len(frame),1200);self.assertTrue(any(frame));self.assertNotEqual(frame,bytes([24]*1200))
        self.assertEqual(studio.path.read_bytes(),path)
        self.assertIsNone(Studio(self.tmp.name).game)
        await self.command({'action':'stop','id':gid});await asyncio.sleep(.06)
        self.assertIsNone(studio.game);self.assertEqual(studio.scene,saved)
        self.assertEqual(studio.frame,bytes([24]*1200))
        await self.command({'action':'start','kind':'tetris'})
        await self.client.post('/api/scene',headers=self.auth,json={'enabled':False})
        self.assertIsNone(studio.game)

    async def test_schedule_blocks_and_pauses_game(self):
        with patch('schedule.datetime') as clock:
            clock.now.return_value=datetime.fromisoformat('2026-11-11T18:30:00+00:00')
            await self.client.post('/api/schedule',headers=self.auth,json={'enabled':True,'on':'18:00','off':'19:00','timezone':'UTC'})
            r=await self.command({'action':'start','kind':'arkanoid'});gid=(await r.json())['game']['id']
            clock.now.return_value=datetime.fromisoformat('2026-11-11T19:00:00+00:00')
            await asyncio.sleep(.06)
            self.assertEqual(self.app['studio'].frame,bytes(1200))
            self.assertEqual(self.app['studio'].game.paused,'schedule')
            self.assertEqual((await self.command({'action':'resume','id':gid})).status,400)
            self.assertEqual((await self.command({'action':'start','kind':'tetris'})).status,400)
            self.assertEqual(self.app['studio'].game.id,gid)
