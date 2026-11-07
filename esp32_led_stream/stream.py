#!/usr/bin/env python3
"""Send 20x20 frames via USB or DDP Wi-Fi. Requires pyserial and Pillow."""
import argparse
import colorsys
import json
from pathlib import Path
import socket
import struct
import time
import zlib

PORT='/dev/ttyUSB0'
SIZE=20

def serial_packet(frame, seq):
    if len(frame)!=1200: raise ValueError('Frame must be 1200 bytes')
    body=struct.pack('<I',seq & 0xffffffff)+frame
    return b'L400'+body+struct.pack('<I',zlib.crc32(body))

def ddp_packet(frame, seq):
    if len(frame)!=1200: raise ValueError('Frame must be 1200 bytes')
    return struct.pack('>BBBBIH',0x41,seq%15+1,0x0b,1,0,len(frame))+frame

def wire_index(x,y,layout):
    if layout=='rows': return y*20+x
    if layout=='rows-serpentine': return y*20+(19-x if y%2 else x)
    if layout=='columns': return x*20+y
    return x*20+(19-y if x%2 else y)

def to_wire(image,layout,level,order):
    from PIL import Image
    image=image.convert('RGB').resize((20,20),Image.Resampling.NEAREST)
    out=bytearray(1200); channels=['RGB'.index(c) for c in order]
    for y in range(20):
        for x in range(20):
            color=image.getpixel((x,y));pos=wire_index(x,y,layout)*3
            out[pos:pos+3]=bytes(color[c]*level//255 for c in channels)
    return bytes(out)

DIGITS=['111101101101111','010110010010111','111001111100111',
        '111001111001111','101101111001001','111100111001111',
        '111100111101111','111001001001001','111101111101111','111101111001111']

def animation(t,pattern):
    from PIL import Image
    image=Image.new('RGB',(20,20))
    if pattern=='counter':
        digits=f'{int(t)%100:02d}'
        for d,ch in enumerate(digits):
            for y in range(5):
                for x in range(3):
                    if DIGITS[int(ch)][y*3+x]=='1':
                        for dy in range(2):
                            for dx in range(2): image.putpixel((3+d*8+x*2+dx,5+y*2+dy),(255,255,255))
    else:
        for y in range(20):
            for x in range(20):
                if pattern=='rainbow':
                    color=tuple(int(v*255) for v in colorsys.hsv_to_rgb((x/20+y/40+t*.3)%1,1,1))
                else:
                    distance=(x+y-int(t*25))%20
                    color=(255,255,255) if distance<3 else (0,0,0)
                image.putpixel((x,y),color)
    return image

class Transport:
    def __init__(self,host=None,port=PORT):
        self.host=host;self.serial=None;self.sock=None
        if host:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sock.settimeout(2)
        else:
            import serial
            s=serial.Serial();s.port=port;s.baudrate=921600;s.timeout=.2
            s.write_timeout=2;s.dtr=False;s.rts=False;s.exclusive=True;s.open()
            self.serial=s;time.sleep(2);s.reset_input_buffer()
    def stats(self):
        if self.host:
            self.sock.sendto(b'stats',(self.host,4049))
            return json.loads(self.sock.recvfrom(4096)[0])
        self.serial.reset_input_buffer();self.serial.write(b'i');self.serial.flush()
        deadline=time.monotonic()+1.2
        retry=time.monotonic()+.5
        latest=None
        while time.monotonic()<deadline:
            if time.monotonic()>=retry:
                self.serial.write(b'i');self.serial.flush();retry=deadline+1
            line=self.serial.readline().decode(errors='replace').strip()
            if line.startswith('{'):
                try:
                    candidate=json.loads(line)
                    if latest is None or candidate['uptime_ms']>=latest['uptime_ms']: latest=candidate
                except json.JSONDecodeError: pass
        if latest is not None: return latest
        raise RuntimeError('No ESP32 stats response at 921600 baud')
    def send(self,frame,seq):
        if self.host: self.sock.sendto(ddp_packet(frame,seq),(self.host,4048))
        else: self.serial.write(serial_packet(frame,seq))
    def close(self):
        if self.sock: self.sock.close()
        if self.serial: self.serial.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',help='ESP32 IP; omit to use USB')
    p.add_argument('--port',default=PORT)
    p.add_argument('--stats',action='store_true')
    p.add_argument('--fps',type=float,default=60)
    p.add_argument('--seconds',type=float,default=15)
    p.add_argument('--brightness',type=int,default=24,help='Maximum channel value 0..255')
    p.add_argument('--pattern',choices=['bars','rainbow','counter'],default='bars')
    p.add_argument('--image',type=Path,help='Image or animated GIF; loop with original GIF timing')
    p.add_argument('--layout',choices=['rows','rows-serpentine','columns','columns-serpentine'],default='columns')
    p.add_argument('--order',choices=['RGB','RBG','GRB','GBR','BRG','BGR'],default='RGB')
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    if not 0<args.fps<=120 or not 0<args.seconds or not 0<=args.brightness<=255:
        p.error('fps 0..120, seconds >0, brightness 0..255 required')
    frames=[];durations=[]
    if args.image:
        from PIL import Image,ImageSequence
        with Image.open(args.image) as image:
            for frame in ImageSequence.Iterator(image):
                frames.append(to_wire(frame.copy(),args.layout,args.brightness,args.order))
                durations.append(max(.01,frame.info.get('duration',100)/1000))
    transport=Transport(args.host,args.port)
    try:
        before=transport.stats()
        if args.stats: print(json.dumps(before,indent=2));return
        print('START',json.dumps(before),flush=True)
        start=time.monotonic();count=0;next_frame=start
        try:
            while time.monotonic()-start<args.seconds:
                t=time.monotonic()-start
                if frames:
                    phase=t%sum(durations);index=0
                    while index<len(frames)-1 and phase>=durations[index]:
                        phase-=durations[index];index+=1
                    frame=frames[index]
                else: frame=to_wire(animation(t,args.pattern),args.layout,args.brightness,args.order)
                transport.send(frame,count);count+=1;next_frame+=1/args.fps
                delay=next_frame-time.monotonic()
                if delay>0: time.sleep(delay)
                elif delay<-.1: next_frame=time.monotonic()
        except KeyboardInterrupt: pass
        if transport.serial: transport.serial.flush()
        duration=time.monotonic()-start
        time.sleep(.3)
        after=transport.stats()
        result={'transport':'wifi_ddp' if args.host else 'usb','requested_fps':args.fps,
                'sent':count,'seconds':round(duration,3),'sent_fps':round(count/duration,2),
                'displayed':after['shown']-before['shown'],
                'displayed_fps_approx':round((after['shown']-before['shown'])/duration,2),
                'received':after['udp_rx' if args.host else 'serial_rx']-before['udp_rx' if args.host else 'serial_rx'],
                'bad':after['bad']-before['bad'],'skipped':after['skipped']-before['skipped'],
                'before':before,'after':after}
        print(json.dumps(result,indent=2))
        if args.report: args.report.write_text(json.dumps(result,indent=2)+'\n')
    finally: transport.close()

if __name__=='__main__': main()
