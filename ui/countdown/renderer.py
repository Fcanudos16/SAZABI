"""Shared HUD drawing for the manual window and embedded search panel."""
import time
from . import theme as t
from .geometry import digit_polygons
from .timer_engine import State, split_cs


class HudRenderer:
    def draw(self):
        c = self.canvas
        c.delete('dynamic')
        scale = self.width/700
        def rect(x,y,w,h,color=t.GREEN,fill=t.BG):
            c.create_rectangle(x*scale,y*scale,(x+w)*scale,(y+h)*scale,outline=color,fill=fill,tags='dynamic')
        def text(x,y,value,size=14,color=t.GREEN,anchor='center',family='Consolas'):
            c.create_text(x*scale,y*scale,text=value,fill=color,anchor=anchor,font=(family,-max(7,round(size*scale)),'bold'),tags='dynamic')
        def line(x,y,x2,y2,color=t.GREEN_MID):
            c.create_line(x*scale,y*scale,x2*scale,y2*scale,fill=color,tags='dynamic')
        alert = not self.research and self.engine.state is State.COMPLETE
        color = (t.RED if int(time.monotonic()*4)%2 else t.RED_DARK) if alert else t.GREEN
        # Original logical 700 x 340 layout, seven-segment geometry and palette.
        if getattr(self, '_background_width', None) != self.width:
            c.delete('all')
            self._background_width = self.width
            for x in range(10,695,5):
                ratio = (x-10)/685
                a,b = (t.PLATE_A,t.PLATE_B) if ratio < .5 else (t.PLATE_B,t.PLATE_C)
                blend = ratio*2 if ratio < .5 else (ratio-.5)*2
                rgb = [round(int(a[i:i+2],16)*(1-blend)+int(b[i:i+2],16)*blend) for i in (1,3,5)]
                shade = '#%02x%02x%02x' % tuple(rgb)
                bottom = 340 if x <= 135 else 340-(x-135)*15/25 if x < 160 else 325 if x < 564 else 275
                c.create_rectangle(x*scale,12*scale,min(x+5,695)*scale,bottom*scale,fill=shade,outline='')
        line(3,12,3,340)
        for x in (55,155,235,350,425,540,640): line(x,3,x,9)
        text(24,30,'SAZABI / SEARCH' if self.research else 'S A Z A B I',15,t.GREEN_LUM,'w')
        rect(153,98,537,169,color)
        text(270,110,'SEARCH TIME ELAPSED:' if self.research else 'ACTIVE TIME REMAINING:',14,anchor='w')
        rect(120,82,140,35)
        text(190,100,'PESQUISA' if self.research else '活動限界まで' if self.jp else 'TIME LIMIT',20,family=self.jp or 'Consolas')
        cs = self.stopwatch.elapsed_cs() if self.research else self.engine.remaining_cs()
        m,s,cs = split_cs(cs)
        digits = str(m)+f'{s:02d}'
        w = min(78,(270-28-(len(digits)-2)*8)/len(digits))
        def digit(x,y,w,h,ch):
            for poly in digit_polygons(x,y,w,h,w*.21,ch):
                c.create_polygon(*[v*scale for point in poly for v in point],fill=color,outline='',tags='dynamic')
        x = 160
        for index,ch in enumerate(digits):
            digit(x,133,w,119,ch); x += w
            if index == len(str(m))-1:
                for y in (162,217): rect(x+10,y,7,7,color,color)
                x += 28
            else: x += 8
        for y in (180,235): rect(435,y,7,7,color,color)
        for index,ch in enumerate(f'{cs:02d}'): digit(448+index*64,158,56,100,ch)
        rect(574,112,108,50)
        text(615,131,'内部' if self.jp else 'INT',30,t.GREEN_LUM,family=self.jp or 'Consolas')
        text(615,152,'INTERNAL',12)
        for y in range(117,154,7): line(655,y+6,678,y)
        rect(574,170,108,30,color)
        state = self.stopwatch.status if self.research else {State.CONFIGURED:'READY'}.get(self.engine.state,self.engine.state.value)
        text(628,185,state,12,color)
        active = (2 if self.stopwatch.running else 0) if self.research else {State.STANDBY:0,State.CONFIGURED:0,State.PAUSED:1,State.RUNNING:2,State.COMPLETE:3}[self.engine.state]
        for index,(x,w,name) in enumerate(((190,58,'STOP'),(275,59,'SLOW'),(363,77,'NORMAL'),(467,65,'RACING'))):
            col = color if index == active else t.GREEN_DIM
            rect(x,275,w,34,col);text(x+w/2,286,name,15,col)
            if index == active: rect(x+4,295,w-8,10,col,col)
        for x,w,label,lit in (() if self.research else ((520,60,'PIN',self.top),(588,58,'AUTO' if self.research else 'SET',self.terminal_open),(654,30,'X',False))):
            rect(x,20,w,22,t.GREEN_MID,t.GREEN if lit else t.BG)
            text(x+w/2,31,label,13,t.BG if lit else t.GREEN)
        if not self.research:
            for offset in (0,7,14): line(692-offset,334,692,334-offset)
