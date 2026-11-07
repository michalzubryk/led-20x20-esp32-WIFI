import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aiohttp.test_utils import TestClient,TestServer
from app import create_app,Studio
from render import DEFAULT,render

class AppTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(self.tmp.name,"test","pass","device-secret")
        self.client=TestClient(TestServer(self.app));await self.client.start_server()
        self.auth={"Authorization":"Basic "+base64.b64encode(b"test:pass").decode()}
    async def asyncTearDown(self):
        await self.client.close();self.tmp.cleanup()
    async def test_auth_and_device(self):
        for path in ("/","/api/state","/api/device/frame","/firmware/led400.bin"):
            self.assertEqual((await self.client.get(path)).status,401)
        self.assertEqual((await self.client.get("/api/device/frame",headers=self.auth)).status,401)
        r=await self.client.get("/api/device/frame",headers={"Authorization":"Bearer device-secret","X-Device-ID":"esp-test","X-Frames-Received":"42"})
        self.assertEqual(len(await r.read()),1200)
        state=await (await self.client.get("/api/state",headers=self.auth)).json()
        self.assertEqual(state["devices"][0]["received"],42)
    async def test_shape_scene_persistence(self):
        shape={"name":"Heart","frames":[[255,0,0]*400],"durationMs":200}
        r=await self.client.post("/api/shapes",headers=self.auth,json=shape);self.assertEqual(r.status,200)
        sid=(await r.json())["id"]
        r=await self.client.post("/api/scene",headers=self.auth,json={"mode":"custom","shapeId":sid,"direction":"none","brightness":24})
        self.assertEqual(r.status,200)
        await asyncio.sleep(.1)
        b=await (await self.client.get("/api/preview",headers=self.auth)).read()
        self.assertEqual(b,bytes([24,0,0]*400))
        persisted=Studio(self.tmp.name);self.assertIn(sid,persisted.shapes);self.assertEqual(persisted.scene["shapeId"],sid)
        r=await self.client.delete("/api/shapes/"+sid,headers=self.auth);self.assertEqual(r.status,200)
        self.assertFalse(self.app["studio"].scene["enabled"])
    async def test_invalid_requests_and_origin(self):
        for data in ({"brightness":999},{"enabled":"yes"},{"mode":[]},{"text":"x"*241}):
            self.assertEqual((await self.client.post("/api/scene",headers=self.auth,json=data)).status,400)
        self.assertEqual((await self.client.post("/api/shapes",headers=self.auth,json={"name":"bad","frames":[[0]],"durationMs":100})).status,400)
        self.assertEqual((await self.client.post("/api/scene",headers={**self.auth,"Origin":"https://evil.invalid"},json={"enabled":False})).status,403)
    async def test_stream_framing(self):
        import struct
        r=await self.client.get("/api/device/stream",headers={"Authorization":"Bearer device-secret","X-Device-ID":"stream-test"})
        data=await r.content.readexactly(2408)
        a=struct.unpack("<I",data[:4])[0];b=struct.unpack("<I",data[1204:1208])[0]
        self.assertGreaterEqual(b,a)
        r.close()
    async def test_failed_save_does_not_change_scene(self):
        from unittest.mock import patch
        old=self.app["studio"].scene.copy()
        with patch("pathlib.Path.write_text",side_effect=OSError("disk")):
            r=await self.client.post("/api/scene",headers=self.auth,json={"text":"lost"})
        self.assertEqual(r.status,507)
        self.assertEqual(old,self.app["studio"].scene)

    async def test_select_image_replaces_slideshow(self):
        shapes=[]
        for name,kind,frames in [("show","slideshow",[[255,0,0]*400,[0,255,0]*400]),("tree","image",[[0,0,255]*400])]:
            r=await self.client.post("/api/shapes",headers=self.auth,json={"name":name,"kind":kind,"frames":frames,"durationMs":50})
            shapes.append(await r.json())
        await self.client.post("/api/shapes/"+shapes[0]["id"]+"/play",headers=self.auth,json={})
        self.assertEqual(self.app["studio"].scene["shapeId"],shapes[0]["id"])
        r=await self.client.post("/api/shapes/"+shapes[1]["id"]+"/play",headers=self.auth,json={})
        self.assertEqual(r.status,200)
        scene=self.app["studio"].scene
        self.assertEqual(scene["shapeId"],shapes[1]["id"])
        self.assertFalse(scene["animate"])
        for t in (0,.1,1,5,20,100):
            self.assertEqual(render(scene,t,self.app["studio"].shapes),bytes([0,0,24]*400))
        self.assertEqual(Studio(self.tmp.name).scene["shapeId"],shapes[1]["id"])
    async def test_animation_stays_with_selected_motif_and_can_freeze(self):
        shape={"name":"tree","kind":"animation","frames":[[255,0,0]*400,[0,255,0]*400],"durationMs":200}
        r=await self.client.post("/api/shapes",headers=self.auth,json=shape);sid=(await r.json())["id"]
        await self.client.post("/api/shapes/"+sid+"/play",headers=self.auth,json={})
        c=self.app["studio"].scene
        self.assertNotEqual(render(c,0,self.app["studio"].shapes),render(c,.25,self.app["studio"].shapes))
        self.assertEqual(render(c,0,self.app["studio"].shapes),render(c,.4,self.app["studio"].shapes))
        await self.client.post("/api/scene",headers=self.auth,json={"animate":False})
        c=self.app["studio"].scene
        self.assertEqual(render(c,0,self.app["studio"].shapes),render(c,99,self.app["studio"].shapes))
    async def test_legacy_slideshow_label(self):
        from app import shape_kind
        self.assertEqual(shape_kind({"name":"Święta · Pokaz wszystkich","frames":[[],[]]}),"slideshow")

    async def test_effects(self):
        for mode in ("text","counter","rainbow","bars","pulse","bounce"):
            for direction in ("left","right","up","down","none"):
                self.assertEqual(len(render({**DEFAULT,"mode":mode,"direction":direction},1.2,{})),1200)
        a=render({**DEFAULT,"direction":"none","brightness":255},1,{})
        b=render({**DEFAULT,"direction":"none","brightness":255,"invert":True},1,{})
        self.assertTrue(all(x+y==255 for x,y in zip(a,b)))

if __name__=="__main__":unittest.main()
