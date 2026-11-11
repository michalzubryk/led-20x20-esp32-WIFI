"""Small server-side games. All renderers return exactly 20x20 RGB bytes."""
import math
import random
import time
import uuid

BLACK = bytes(1200)
COLORS = [(40,210,255),(255,220,40),(185,70,255),(50,230,100),
          (255,65,75),(60,110,255),(255,145,30)]
PIECES = [('....','####','....','....'),('##','##'),('.#.','###','...'),
          ('.##','##.','...'),('##.','.##','...'),('#..','###','...'),('..#','###','...')]


def pixel(frame,x,y,color):
    if 0 <= x < 20 and 0 <= y < 20:
        frame[(y*20+x)*3:(y*20+x)*3+3] = bytes(color)


class Breakout:
    def __init__(self):
        self.paddle=9.5;self.score=0;self.lives=3;self.phase='ready'
        self.bricks={(c,r) for r in range(3) for c in range(5)}
        self.x=self.paddle;self.y=17.;self.vx=3.;self.vy=-7.

    def control(self,action,value=None):
        if action=='position':self.paddle=max(2.,min(17.,float(value)))
        elif action=='left':self.paddle=max(2.,self.paddle-2)
        elif action=='right':self.paddle=min(17.,self.paddle+2)
        elif action=='launch' and self.phase=='ready':self.phase='playing'
        if self.phase=='ready':self.x=self.paddle

    def tick(self,dt):
        if self.phase!='playing':return
        # Substeps avoid passing through one-pixel bricks between frames.
        steps=max(1,math.ceil(dt/.01));step=dt/steps
        for _ in range(steps):
            nx=self.x+self.vx*step;ny=self.y+self.vy*step
            if nx<0 or nx>19:
                self.vx=-self.vx;nx=max(0.,min(19.,nx))
            if ny<0:self.vy=abs(self.vy);ny=0.
            if self.vy>0 and self.y<17.5<=ny and abs(nx-self.paddle)<=2.7:
                offset=max(-1.,min(1.,(nx-self.paddle)/2.5))
                self.vx=offset*5.5;self.vy=-math.sqrt(8**2-self.vx**2);ny=17.4
            for c,r in sorted(self.bricks):
                left,right,top,bottom=c*4-.45,c*4+2.45,3+r*2-.45,3+r*2+.45
                if left<=nx<=right and top<=ny<=bottom:
                    self.bricks.remove((c,r));self.score+=10
                    if self.x<left or self.x>right:self.vx=-self.vx;nx=self.x
                    else:self.vy=-self.vy;ny=self.y
                    break
            self.x,self.y=nx,ny
            if not self.bricks:self.phase='won';return
            if self.y>19.5:
                self.lives-=1;self.phase='ready' if self.lives else 'over'
                self.x=self.paddle;self.y=17.;self.vx=3.;self.vy=-7.;return

    def draw(self):
        f=bytearray(BLACK)
        for c,r in self.bricks:
            for x in range(c*4,c*4+3):pixel(f,x,3+r*2,COLORS[r+1])
        for x in range(round(self.paddle)-2,round(self.paddle)+3):pixel(f,x,18,(40,210,255))
        if self.phase!='over':pixel(f,round(self.x),round(self.y),(255,255,255))
        for x in range(self.lives):pixel(f,x*2,0,(255,60,90))
        return f

    def status(self):
        return dict(score=self.score,lives=self.lives,phase=self.phase,remaining=len(self.bricks),paddle=self.paddle)


class Tetris:
    def __init__(self,rng=None):
        self.rng=rng or random.Random();self.bag=[]
        self.board=[[0]*10 for _ in range(20)]
        self.score=0;self.lines=0;self.phase='playing';self.fall=0.
        self.next_piece=self.take();self.spawn()

    def take(self):
        if not self.bag:
            self.bag=list(range(7));self.rng.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self):
        self.kind=self.next_piece;self.next_piece=self.take()
        self.cells=[(x,y) for y,row in enumerate(PIECES[self.kind]) for x,c in enumerate(row) if c=='#']
        self.size=len(PIECES[self.kind]);self.x=3;self.y=0;self.fall=0.
        if not self.fits(self.x,self.y,self.cells):self.phase='over'

    def fits(self,x,y,cells):
        return all(0<=x+dx<10 and 0<=y+dy<20 and not self.board[y+dy][x+dx] for dx,dy in cells)

    def move(self,dx,dy):
        if self.fits(self.x+dx,self.y+dy,self.cells):self.x+=dx;self.y+=dy;return True
        return False

    def lock(self):
        for dx,dy in self.cells:self.board[self.y+dy][self.x+dx]=self.kind+1
        rows=[row for row in self.board if not all(row)]
        count=20-len(rows)
        self.score+=[0,100,300,500,800][count]*(1+self.lines//10)
        self.lines+=count;self.board=[[0]*10 for _ in range(count)]+rows
        self.spawn()

    def control(self,action,value=None):
        if self.phase!='playing':return
        if action in ('left','right'):self.move(-1 if action=='left' else 1,0)
        elif action=='rotate':
            if self.kind==1:return
            rotated=[(self.size-1-y,x) for x,y in self.cells]
            for kick in (0,-1,1,-2,2):
                if self.fits(self.x+kick,self.y,rotated):self.cells=rotated;self.x+=kick;break
        elif action=='down':
            if self.move(0,1):self.score+=1
            else:self.lock()
            self.fall=0.
        elif action=='drop':
            while self.move(0,1):self.score+=2
            self.lock()

    def tick(self,dt):
        if self.phase!='playing':return
        self.fall+=dt;interval=max(.15,.8-.06*(self.lines//10))
        if self.fall>=interval:
            self.fall-=interval
            if not self.move(0,1):self.lock()

    def draw(self):
        f=bytearray(BLACK)
        for y in range(20):
            for x in (4,15):pixel(f,x,y,(35,45,60))
            for x,value in enumerate(self.board[y]):
                if value:pixel(f,x+5,y,COLORS[value-1])
        if self.phase=='playing':
            gy=self.y
            while self.fits(self.x,gy+1,self.cells):gy+=1
            for x,y in self.cells:pixel(f,self.x+x+5,gy+y,tuple(c//6 for c in COLORS[self.kind]))
            for x,y in self.cells:pixel(f,self.x+x+5,self.y+y,COLORS[self.kind])
        for y,row in enumerate(PIECES[self.next_piece]):
            for x,c in enumerate(row):
                if c=='#':pixel(f,16+x,2+y,COLORS[self.next_piece])
        return f

    def status(self):
        return dict(score=self.score,lines=self.lines,level=1+self.lines//10,phase=self.phase,next=self.next_piece)


class GameSession:
    """One shared display, one transient game. No changes to saved scenes."""
    def __init__(self,kind,brightness=24,clock=time.monotonic):
        if kind not in ('arkanoid','tetris'):raise ValueError('Wybierz Arkanoida lub Tetrisa')
        self.id=uuid.uuid4().hex;self.kind=kind
        self.engine=Breakout() if kind=='arkanoid' else Tetris()
        self.clock=clock;self.last=self.last_seen=clock();self.paused=''
        self.brightness=brightness

    def tick(self,now,allowed):
        dt=max(0.,min(.1,now-self.last));self.last=now
        if not allowed:self.paused='schedule'
        elif not self.paused and now-self.last_seen>8:self.paused='idle'
        if not self.paused:self.engine.tick(dt)

    def command(self,action,value=None,allowed=True):
        actions={'heartbeat','pause','resume','brightness','left','right'}
        actions|={'position','launch'} if self.kind=='arkanoid' else {'rotate','down','drop'}
        if action not in actions:raise ValueError('Nieznane sterowanie gry')
        if action=='position' and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=19):
            raise ValueError('Pozycja paletki: 0–19')
        if action=='brightness' and (type(value) is not int or not 0<=value<=255):raise ValueError('Jasność: 0–255')
        # Enforce timeouts here too: a late packet must not bypass a pause.
        self.tick(self.clock(),allowed);self.last_seen=self.clock()
        if action=='pause':self.paused='manual'
        elif action=='resume':
            if not allowed:raise ValueError('Poza godzinami świecenia — zmień harmonogram, aby grać')
            self.paused='';self.last=self.clock()
        elif action=='brightness':self.brightness=value
        elif action!='heartbeat' and not self.paused:self.engine.control(action,value)

    def status(self):
        return dict(active=True,id=self.id,kind=self.kind,paused=self.paused,brightness=self.brightness,**self.engine.status())

    def frame(self):
        frame=self.engine.draw()
        phase=self.engine.phase
        if phase in ('won','over'):
            color=(30,255,100) if phase=='won' else (255,35,50)
            for x in range(20):pixel(frame,x,19,color)
        if self.paused:
            for x in (8,11):
                for y in range(8,12):pixel(frame,x,y,(255,180,40))
        return bytes(v*self.brightness//255 for v in frame)
