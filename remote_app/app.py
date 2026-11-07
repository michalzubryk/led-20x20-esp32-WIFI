import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import ssl
import struct
import time
import uuid
from aiohttp import web
from render import DEFAULT,validate_scene,render
from schedule import DEFAULT_SCHEDULE,validate_schedule,schedule_status

def shape_kind(shape):
    if "kind" in shape:return shape["kind"]
    if shape["name"]=="Święta · Pokaz wszystkich":return "slideshow"
    return "animation" if len(shape["frames"])>1 else "image"

class Studio:
    def __init__(self,directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/"studio.json";self.scene=DEFAULT.copy();self.shapes={}
        self.schedule=DEFAULT_SCHEDULE.copy()
        self.epoch=time.monotonic();self.sequence=0;self.frame=bytes(1200);self.devices={}
        if self.path.exists():
            state=json.loads(self.path.read_text())
            self.scene=validate_scene(state["scene"],DEFAULT);self.shapes=state["shapes"]
            self.schedule=validate_schedule(state.get("schedule",{}))
    def save(self,scene=None,shapes=None,schedule=None):
        scene=self.scene if scene is None else scene
        shapes=self.shapes if shapes is None else shapes
        schedule=self.schedule if schedule is None else schedule
        temp=self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(dict(scene=scene,shapes=shapes,schedule=schedule),ensure_ascii=False))
        temp.replace(self.path)
        self.scene=scene;self.shapes=shapes;self.schedule=schedule
    def render_frame(self,elapsed,now=None):
        if not schedule_status(self.schedule,now)["active"]:return bytes(1200)
        return render(self.scene,elapsed,self.shapes)
    def metadata(self):
        return [dict(id=s["id"],name=s["name"],frames=len(s["frames"]),durationMs=s["durationMs"],kind=shape_kind(s)) for s in self.shapes.values()]
    def status(self):
        now=time.monotonic()
        return dict(scene=self.scene,schedule=schedule_status(self.schedule),shapes=self.metadata(),sequence=self.sequence,
            devices=[dict(id=k,online=now-v["last"]<5,ageSeconds=round(now-v["last"],1),
                          received=v.get("received",0),framesSent=v.get("framesSent",0),requests=v["requests"]) for k,v in self.devices.items()])

def validate_shape(data):
    if not isinstance(data,dict) or set(data)-{"name","frames","durationMs","kind"}:raise ValueError("Niepoprawny kształt")
    name=data.get("name");frames=data.get("frames");duration=data.get("durationMs",200)
    if not isinstance(name,str) or not name.strip() or len(name)>60:raise ValueError("Nazwa: 1–60 znaków")
    if type(duration) is not int or not 50<=duration<=2000:raise ValueError("Czas klatki 50–2000 ms")
    if not isinstance(frames,list) or not 1<=len(frames)<=32:raise ValueError("Od 1 do 32 klatek")
    for f in frames:
        if not isinstance(f,list) or len(f)!=1200 or any(type(v) is not int or not 0<=v<=255 for v in f):
            raise ValueError("Klatka: 1200 kanałów RGB 0–255")
    kind=data.get("kind","animation" if len(frames)>1 else "image")
    if kind not in ("image","animation","slideshow") or (kind=="image" and len(frames)!=1):
        raise ValueError("Niepoprawny rodzaj grafiki")
    return dict(name=name.strip(),frames=frames,durationMs=duration,kind=kind)

def create_app(directory=None,user=None,password=None,token=None):
    user=user or os.environ["BASIC_USER"];password=password or os.environ["BASIC_PASSWORD"];token=token or os.environ["DEVICE_TOKEN"]
    basic="Basic "+base64.b64encode((user+":"+password).encode()).decode()
    studio=Studio(directory or os.getenv("DATA_DIR","data"))
    @web.middleware
    async def guard(request,handler):
        if request.path!="/health":
            supplied=request.headers.get("Authorization","")
            expected="Bearer "+token if request.path.startswith("/api/device/") else basic
            if not hmac.compare_digest(supplied.encode(),expected.encode()):
                raise web.HTTPUnauthorized(headers={"WWW-Authenticate":'Basic realm="LED Studio", charset="UTF-8"'})
            if request.method not in ("GET","HEAD"):
                origin=request.headers.get("Origin")
                if origin and origin!=f"{request.scheme}://{request.host}":raise web.HTTPForbidden()
        try:response=await handler(request)
        except (ValueError,TypeError,KeyError) as exc:return web.json_response({"error":str(exc)},status=400)
        except OSError:return web.json_response({"error":"Nie udało się zapisać na dysku serwera"},status=507)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="DENY"
        return response
    app=web.Application(middlewares=[guard],client_max_size=1024*1024)
    app["studio"]=studio
    async def health(r):return web.json_response({"ok":True})
    async def index(r):return web.FileResponse(Path(__file__).parent/"static/index.html")
    async def asset(r):
        if r.match_info["name"] not in ("app.js","style.css"):raise web.HTTPNotFound()
        return web.FileResponse(Path(__file__).parent/"static"/r.match_info["name"])
    async def state(r):return web.json_response(studio.status())
    async def update(r):
        c=validate_scene(await r.json(),studio.scene)
        if c["mode"]=="custom" and c["shapeId"] not in studio.shapes:raise ValueError("Wybierz zapisany kształt")
        studio.save(scene=c);studio.epoch=time.monotonic()
        return web.json_response(studio.status())
    async def update_schedule(r):
        config=validate_schedule(await r.json(),studio.schedule)
        studio.save(schedule=config)
        return web.json_response(studio.status())
    async def preview(r):return web.Response(body=studio.frame,content_type="application/octet-stream")
    async def save_shape(r):
        shape=validate_shape(await r.json());sid=r.match_info.get("id") or uuid.uuid4().hex
        if r.method=="PUT" and sid not in studio.shapes:raise web.HTTPNotFound()
        if sid not in studio.shapes and len(studio.shapes)>=100:raise ValueError("Limit 100 kształtów")
        shape["id"]=sid;studio.save(shapes={**studio.shapes,sid:shape})
        return web.json_response(shape)
    async def play_shape(r):
        sid=r.match_info["id"];shape=studio.shapes.get(sid)
        if not shape:raise web.HTTPNotFound()
        # A deliberate selection replaces the previous slideshow, resets effects
        # and never advances to a different shape.
        c=validate_scene(dict(mode="custom",shapeId=sid,direction="none",enabled=True,
                              blink=False,invert=False,animate=len(shape["frames"])>1),studio.scene)
        studio.save(scene=c);studio.epoch=time.monotonic()
        return web.json_response(studio.status())
    async def get_shape(r):
        shape=studio.shapes.get(r.match_info["id"])
        if not shape:raise web.HTTPNotFound()
        return web.json_response({**shape,"kind":shape_kind(shape)})
    async def delete_shape(r):
        sid=r.match_info["id"]
        if sid not in studio.shapes:raise web.HTTPNotFound()
        updated=studio.shapes.copy();del updated[sid]
        scene=studio.scene.copy()
        if scene["shapeId"]==sid:scene.update(shapeId="",mode="text",enabled=False)
        studio.save(scene=scene,shapes=updated);return web.json_response({"ok":True})
    async def device_frame(r):
        did=r.headers.get("X-Device-ID","unknown")
        if not re.fullmatch(r"[a-zA-Z0-9:-]{1,40}",did):raise ValueError("device")
        # Keep only recently active devices, bound memory even with a leaked key.
        now=time.monotonic()
        studio.devices={k:v for k,v in studio.devices.items() if now-v["last"]<3600}
        if did not in studio.devices and len(studio.devices)>=100:raise web.HTTPTooManyRequests()
        d=studio.devices.setdefault(did,{"requests":0})
        d.update(last=now,requests=d["requests"]+1,received=int(r.headers.get("X-Frames-Received","0")))
        return web.Response(body=studio.frame,content_type="application/octet-stream",headers={"X-Frame-Sequence":str(studio.sequence)})
    async def device_stream(r):
        did=r.headers.get("X-Device-ID","unknown")
        if not re.fullmatch(r"[a-zA-Z0-9:-]{1,40}",did):raise ValueError("device")
        now=time.monotonic()
        studio.devices={k:v for k,v in studio.devices.items() if now-v["last"]<3600}
        if did not in studio.devices and len(studio.devices)>=100:raise web.HTTPTooManyRequests()
        d=studio.devices.setdefault(did,{"requests":0,"framesSent":0})
        # One persistent stream per physical device; stale streams cannot overwrite status.
        session=uuid.uuid4().hex
        d.update(last=now,session=session,requests=d["requests"]+1,received=int(r.headers.get("X-Frames-Received","0")))
        response=web.StreamResponse(headers={"Content-Type":"application/octet-stream","Cache-Control":"no-store"})
        response.force_close()
        await response.prepare(r)
        try:
            while d.get("session")==session:
                await asyncio.wait_for(response.write(struct.pack("<I",studio.sequence & 0xffffffff)+studio.frame),timeout=2)
                d.update(last=time.monotonic(),framesSent=d.get("framesSent",0)+1)
                await asyncio.sleep(.05)
        except (ConnectionError,asyncio.TimeoutError):
            pass
        finally:
            if d.get("session")==session:d["last"]=time.monotonic()-10
        return response
    async def firmware(r):
        path=Path(os.getenv("FIRMWARE_DIR","releases"))/"led400.bin"
        if not path.exists():raise web.HTTPNotFound(text="Brak wydania firmware")
        data=path.read_bytes()
        return web.Response(body=data,content_type="application/octet-stream",headers={
            "Content-Disposition":'attachment; filename="led400.bin"',
            "X-Firmware-SHA256":hashlib.sha256(data).hexdigest()})
    async def firmware_info(r):
        path=Path(os.getenv("FIRMWARE_DIR","releases"))/"led400.bin"
        if not path.exists():return web.json_response({"available":False})
        data=path.read_bytes()
        return web.json_response({"available":True,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"url":"/firmware/led400.bin"})
    app.router.add_get("/health",health);app.router.add_get("/",index)
    app.router.add_get("/static/{name}",asset)
    app.router.add_get("/api/state",state);app.router.add_post("/api/scene",update)
    app.router.add_post("/api/schedule",update_schedule)
    app.router.add_get("/api/preview",preview)
    app.router.add_post("/api/shapes",save_shape);app.router.add_put("/api/shapes/{id}",save_shape)
    app.router.add_post("/api/shapes/{id}/play",play_shape)
    app.router.add_get("/api/shapes/{id}",get_shape);app.router.add_delete("/api/shapes/{id}",delete_shape)
    app.router.add_get("/api/device/frame",device_frame)
    app.router.add_get("/api/device/stream",device_stream)
    app.router.add_get("/api/device/firmware",firmware)
    app.router.add_get("/firmware/led400.bin",firmware);app.router.add_get("/api/firmware",firmware_info)
    async def generator():
        while True:
            start=time.monotonic()
            studio.frame=studio.render_frame(start-studio.epoch);studio.sequence+=1
            await asyncio.sleep(max(.001,.05-(time.monotonic()-start)))
    async def lifecycle(app):
        task=asyncio.create_task(generator())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):await task
    app.cleanup_ctx.append(lifecycle)
    return app

if __name__=="__main__":
    app=create_app();cert=os.getenv("CERT_FILE");ctx=None
    if cert:
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert,os.environ["KEY_FILE"])
        async def reload_cert(app):
            async def loop():
                while True:
                    await asyncio.sleep(3600)
                    try:ctx.load_cert_chain(cert,os.environ["KEY_FILE"])
                    except (OSError,ssl.SSLError):print("Certificate reload failed",flush=True)
            task=asyncio.create_task(loop())
            yield
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task
        app.cleanup_ctx.append(reload_cert)
    web.run_app(app,host=os.getenv("BIND","0.0.0.0"),port=int(os.getenv("PORT","8443")),ssl_context=ctx,access_log=None)
