"""Painter-based icons and time-based desktop animations; no emoji font dependency."""
import math,time
from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QFont, QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QAbstractButton, QLabel, QGraphicsOpacityEffect

PALETTE={'background':'#22252b','surface':'#2d323b','border':'#414855','text':'#e5e8ed','muted':'#959ba8','accent':'#ccd9ec','button':'#ccd0d7','button_text':'#24272f','map':'#303743','selected':'#3b4555','good':'#43c89e','medium':'#efa858','bad':'#ed737d'}
FLAG_RADIUS=4
def set_palette(colors,radius=4):
    global PALETTE,FLAG_RADIUS
    PALETTE=dict(colors);FLAG_RADIUS=radius;flag_pixmap.cache_clear()

def icon(kind,color=None):
    color=color or PALETTE['text']
    pix=QPixmap(48,48);pix.fill(Qt.transparent);p=QPainter(pix);draw_icon(p,kind,color,48);p.end();return QIcon(pix)

class FadeLabel(QLabel):
    def __init__(self,text='',parent=None):
        super().__init__(text,parent);self.effect=QGraphicsOpacityEffect(self);self.effect.setOpacity(1.);self.setGraphicsEffect(self.effect);self.anim=QPropertyAnimation(self.effect,b'opacity',self);self.anim.setDuration(250);self.anim.setEasingCurve(QEasingCurve.OutCubic)
    def transition(self,text):
        if self.text()==text:return
        self.setText(text);self.anim.stop();self.anim.setStartValue(.2);self.anim.setEndValue(1.);self.anim.start()

class AnimatedButton(QAbstractButton):
    def __init__(self,parent=None):
        super().__init__(parent);self.setCursor(Qt.PointingHandCursor);self.setAccessibleName('Connect or disconnect');self._blend=0.;self._hover=0.;self.phase=0.;self.mode='idle'
        self.blend_animation=QPropertyAnimation(self,b'blend',self);self.blend_animation.setDuration(500);self.blend_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.hover_animation=QPropertyAnimation(self,b'hover',self);self.hover_animation.setDuration(200);self.hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.motion=True;self.last_tick=time.monotonic();self.timer=QTimer(self);self.timer.setInterval(16);self.timer.timeout.connect(self.tick)
    def get_blend(self):return self._blend
    def set_blend(self,v):self._blend=v;self.update()
    blend=Property(float,get_blend,set_blend)
    def get_hover(self):return self._hover
    def set_hover(self,v):self._hover=v;self.update()
    hover=Property(float,get_hover,set_hover)
    def enterEvent(self,event):self.animate_hover(1.);super().enterEvent(event)
    def leaveEvent(self,event):self.animate_hover(0.);super().leaveEvent(event)
    def animate_hover(self,target):self.hover_animation.stop();self.hover_animation.setStartValue(self._hover);self.hover_animation.setEndValue(target);self.hover_animation.start()
    def tick(self):
        now=time.monotonic();self.phase=(self.phase+min(.1,now-self.last_tick)*230)%360;self.last_tick=now;self.update()
    def hideEvent(self,event):
        if hasattr(self,'timer'):self.timer.stop()
        super().hideEvent(event)
    def showEvent(self,event):
        super().showEvent(event)
        if self.motion and self.mode in ('connecting','disconnecting'):self.last_tick=time.monotonic();self.timer.start()
    def set_mode(self,mode):
        self.mode=mode;self.setProperty('connected',mode=='connected');self.blend_animation.stop();self.blend_animation.setStartValue(self._blend);self.blend_animation.setEndValue(1. if mode=='connected' else 0.);self.blend_animation.start()
        if self.motion and self.isVisible() and mode in ('connecting','disconnecting'):self.last_tick=time.monotonic();self.timer.start()
        else:self.timer.stop()
        self.update()
class ActionButton(AnimatedButton):
    """Compact animated connect CTA in the connection card."""
    def __init__(self,parent=None):
        super().__init__(parent);self.idle_text='Connect to fastest VPN';self.setFixedSize(304,46);self.setText(self.idle_text)
    def set_caption(self,text):
        self.idle_text=text
        if self.mode=='idle':self.setText(text);self.setAccessibleName(text)
        self.update()
    def set_mode(self,mode):
        super().set_mode(mode);text={'idle':self.idle_text,'connecting':'Connecting…','connected':'Disconnect','disconnecting':'Disconnecting…'}[mode];self.setText(text);self.setAccessibleName(text)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        base=QColor(PALETTE['button']);target=QColor(PALETTE['accent'])
        mix=self._blend*.55
        tone=QColor(int(base.red()*(1-mix)+target.red()*mix),int(base.green()*(1-mix)+target.green()*mix),int(base.blue()*(1-mix)+target.blue()*mix))
        tone=tone.lighter(int(100+self._hover*6)) if not self.isDown() else tone.darker(107)
        p.setPen(Qt.NoPen);p.setBrush(tone);p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),10,10)
        text={'idle':self.idle_text,'connecting':'Connecting…','connected':'Disconnect','disconnecting':'Disconnecting…'}[self.mode]
        color=PALETTE['button_text'];p.setPen(QColor(color));font=QFont('Segoe UI',11);font.setWeight(QFont.DemiBold);p.setFont(font)
        p.drawText(QRectF(40,0,self.width()-80,self.height()),Qt.AlignCenter,p.fontMetrics().elidedText(text,Qt.ElideRight,self.width()-80))
        p.save();p.translate(17,12);draw_icon(p,'shield' if self.mode=='connected' else 'power',color,22);p.restore()
        if self.mode in ('connecting','disconnecting'):
            # One small arc, rotating at a time-based rate; no expanding ripple.
            p.setPen(QPen(QColor(color),1.8,Qt.SolidLine,Qt.RoundCap));p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(self.width()-34,15,16,16),int(-self.phase*16),250*16)

# All SVGs are bundled, rendered locally and never fetched by the running app.
from pathlib import Path
from functools import lru_cache
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray,Signal
ASSETS=Path(__file__).resolve().parent/'assets'
ICON_NAMES={'gear':'settings','book':'book','fast':'zap','transport':'shield','plus':'plus','search':'search','shield':'shield','edit':'pencil','trash':'trash-2','star':'star','up':'arrow-up','down':'arrow-down','more':'ellipsis-vertical'}
@lru_cache(maxsize=128)
def svg_renderer(filename,color=None):
    data=Path(filename).read_bytes()
    if color:data=data.replace(b'currentColor',color.encode())
    return QSvgRenderer(QByteArray(data))
def draw_icon(p,kind,color='#c8cbd2',size=24):
    path=ASSETS/'icons'/f'{ICON_NAMES.get(kind,kind)}.svg'
    if kind=='star-filled':
        data=(ASSETS/'icons/star.svg').read_bytes().replace(b'fill="none"',b'fill="currentColor"').replace(b'currentColor',color.encode())
        QSvgRenderer(QByteArray(data)).render(p,QRectF(0,0,size,size))
    else:svg_renderer(str(path),color).render(p,QRectF(0,0,size,size))
@lru_cache(maxsize=512)
def flag_pixmap(code,width=36,height=27):
    name=code.lower() if len(code)==2 and code.isascii() and code.isalpha() else 'unknown';path=ASSETS/'flags'/f'{name}.svg'
    if not path.is_file():path=ASSETS/'flags'/'unknown.svg'
    pix=QPixmap(width,height);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing)
    clip=QPainterPath();clip.addRoundedRect(QRectF(0,0,width,height),FLAG_RADIUS,FLAG_RADIUS);p.setClipPath(clip);svg_renderer(str(path)).render(p,QRectF(0,0,width,height));p.end();return pix
@lru_cache(maxsize=1)
def logo_icon():
    return QIcon(str(ASSETS/'lumen-shield.png'))

class QualityWidget(QWidget):
    def __init__(self,tooltip,parent=None):super().__init__(parent);self.tooltip=tooltip;self.setStyleSheet('background:transparent;')
    def enterEvent(self,event):self.setToolTip(self.tooltip());super().enterEvent(event)

class SignalBars(QWidget):
    def __init__(self,latency=None,good=80,medium=180,parent=None):
        super().__init__(parent);self.setFixedSize(19,20)
        from latency import level
        self.bars=level(latency,good,medium)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        color=PALETTE[{3:'good',2:'medium',1:'bad',0:'muted'}[self.bars]]
        for index,height in enumerate((6,11,16)):
            ink=QColor(color);ink.setAlpha(255 if index<self.bars else 55);p.setBrush(ink);p.drawRoundedRect(QRectF(index*6+1,18-height,3,height),1,1)

def fast_pixmap(width=36,height=27):
    pix=QPixmap(width,height);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);p.setBrush(QColor(PALETTE['selected']));p.drawRoundedRect(QRectF(0,0,width,height),FLAG_RADIUS,FLAG_RADIUS);p.translate((width-20)/2,(height-20)/2);draw_icon(p,'fast',PALETTE['accent'],20);p.end();return pix

class WorldMap(QWidget):
    locationClicked=Signal(str);emptyClicked=Signal()
    def __init__(self,parent=None):
        import json
        super().__init__(parent);self.setMinimumHeight(230);self.setMouseTracking(True);self.locations=[];self.selected=None;self.hovered=None;self.mode='idle';self.phase=0.;self._point=QPointF(0,0)
        self.path=QPainterPath();self.centers=json.loads((ASSETS/'countries.json').read_text())
        from PySide6.QtCore import QByteArray,QDataStream,QIODevice
        cached=ASSETS/'map.path'
        if cached.is_file():
            cached_bytes=QByteArray(cached.read_bytes());stream=QDataStream(cached_bytes,QIODevice.ReadOnly);stream.setVersion(QDataStream.Qt_6_0);stream>>self.path
            if stream.status()!=QDataStream.Ok:raise ValueError('Bundled map geometry is damaged.')
        else:
            data=json.loads((ASSETS/'world.geojson').read_text())
            for feature in data['features']:
                g=feature['geometry'];polygons=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
                for polygon in polygons:
                    for ring in polygon:
                        if not ring or max(p[1] for p in ring)<-60:continue
                        self.path.moveTo(ring[0][0],-ring[0][1])
                        for lon,lat,*_ in ring[1:]:self.path.lineTo(lon,-lat)
                        self.path.closeSubpath()
        self.move_animation=QPropertyAnimation(self,b'point',self);self.move_animation.setDuration(450);self.move_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.last_tick=time.monotonic();self.timer=QTimer(self);self.timer.setInterval(30);self.timer.timeout.connect(self.tick)
        self._land_key=None;self._land=None;self._markers_key=None;self._markers=[];self.motion=True;self.pulse=True;self.tooltips_enabled=True
    def get_point(self):return self._point
    def set_point(self,value):self._point=value;self.update()
    point=Property(QPointF,get_point,set_point)
    def set_locations(self,items):
        self.locations=[{'id':i['id'],'country_code':i.get('country_code',''),'country':i.get('country',''),'name':i['name'],'city':i.get('city','')} for i in items];self._markers_key=None;self.update()
    def select_server(self,ident):
        previous=self.selected;self.selected=ident
        if previous!=ident:
            self.move_animation.stop()
            # Opacity/halo progression uses the existing point property as a scalar pair.
            self.move_animation.setStartValue(QPointF(0,0));self.move_animation.setEndValue(QPointF(1,1));self.move_animation.start()
        self.update()
    def set_mode(self,mode):
        self.mode=mode
        if self.motion and self.pulse and mode in ('connected','connecting','disconnecting') and self.isVisible():self.timer.start()
        else:self.timer.stop()
        self.update()
    def showEvent(self,event):
        super().showEvent(event)
        if self.motion and self.pulse and self.mode in ('connected','connecting','disconnecting'):self.timer.start()
    def hideEvent(self,event):
        self.timer.stop();super().hideEvent(event)
    def tick(self):
        if not self.isVisible() or self.window().isMinimized():return
        now=time.monotonic();self.phase=(self.phase+min(.1,now-self.last_tick)*60)%100;self.last_tick=now
        point=next((pos for item,pos in self.marker_positions() if item['id']==self.selected),None)
        if point:self.update(QRectF(point.x()-50,point.y()-50,100,100).toAlignedRect())
    def marker_positions(self):
        key=(self.width(),self.height())
        if self._markers_key==key:return self._markers
        scale=min((self.width()-28)/360,(self.height()-28)/155);ox=self.width()/2;oy=self.height()/2+8;groups={};result=[]
        for item in self.locations:
            code=item['country_code'].upper()
            if code in self.centers:groups.setdefault(code,[]).append(item)
        for code,items in groups.items():
            c=self.centers[code];x=ox+c['lon']*scale;y=oy-c['lat']*scale
            for index,item in enumerate(items):
                angle=index*2*math.pi/len(items);radius=16 if len(items)>1 else 0
                result.append((item,QPointF(x+radius*math.cos(angle),y+radius*math.sin(angle))))
        self._markers_key=key;self._markers=result;return result
    def hit(self,point):
        hits=[(math.hypot(p.x()-point.x(),p.y()-point.y()),item) for item,p in self.marker_positions()]
        if not hits:return None
        distance,item=min(hits,key=lambda h:h[0]);return item if distance<=14 else None
    def mouseMoveEvent(self,event):
        item=self.hit(event.position());self.hovered=item['id'] if item else None;self.setCursor(Qt.PointingHandCursor if item else Qt.ArrowCursor)
        self.update();super().mouseMoveEvent(event)
    def leaveEvent(self,event):self.hovered=None;self.update();super().leaveEvent(event)
    def mousePressEvent(self,event):
        item=self.hit(event.position())
        if event.button()==Qt.LeftButton and item:self.locationClicked.emit(item['id']);event.accept();return
        if event.button()==Qt.LeftButton:self.emptyClicked.emit();event.accept();return
        super().mousePressEvent(event)
    def paintEvent(self,event):
        ratio=self.devicePixelRatioF();key=(self.width(),self.height(),ratio)
        if self._land_key!=key:
            self._land=QPixmap(math.ceil(self.width()*ratio),math.ceil(self.height()*ratio));self._land.setDevicePixelRatio(ratio);self._land.fill(Qt.transparent)
            land=QPainter(self._land);land.setRenderHint(QPainter.Antialiasing)
            scale=min((self.width()-28)/360,(self.height()-28)/155)
            land.translate(self.width()/2,self.height()/2+8);land.scale(scale,scale);land.setPen(QPen(QColor(PALETTE['map']),.45));land.setBrush(QColor(PALETTE['map']));land.drawPath(self.path);land.end()
            self._land_key=key
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.drawPixmap(0,0,self._land)
        for item,position in self.marker_positions():
            x=position.x();y=position.y();selected=item['id']==self.selected;hover=item['id']==self.hovered
            if selected and self.mode!='idle' and self.motion and self.pulse:
                r=10+math.sin(self.phase/100*math.pi*2)*2;halo=QColor(PALETTE['accent']);halo.setAlpha(65);p.setPen(QPen(halo,1.5));p.setBrush(Qt.NoBrush);p.drawEllipse(QRectF(x-r,y-r,r*2,r*2))
            r=5.5 if selected or hover else 4;p.setPen(QPen(QColor(PALETTE['accent'] if selected or hover else PALETTE['muted']),1.3));p.setBrush(QColor(PALETTE['accent'] if selected or hover else PALETTE['muted']));p.drawEllipse(QRectF(x-r,y-r,2*r,2*r))
            if selected or hover:p.setPen(QPen(QColor(211,227,247,55),1));p.setBrush(Qt.NoBrush);p.drawEllipse(QRectF(x-10,y-10,20,20))

        if self.hovered and self.tooltips_enabled:
            pair=next(((item,pos) for item,pos in self.marker_positions() if item['id']==self.hovered),None)
            if pair:
                item,pos=pair;title=item['country'] or 'Country unknown';subtitle=' · '.join(dict.fromkeys(v for v in [item['city'],item['name']] if v and v!=title))
                width=min(250,self.width()-12);height=62 if subtitle else 44;x=max(6,min(self.width()-width-6,pos.x()-width/2));y=pos.y()-height-18
                if y<6:y=pos.y()+18
                y=max(6,min(self.height()-height-6,y));rect=QRectF(x,y,width,height)
                p.setPen(QPen(QColor(PALETTE['border']),1));p.setBrush(QColor(PALETTE['surface']));p.drawRoundedRect(rect,10,10);p.drawPixmap(int(x+12),int(y+12),flag_pixmap(item['country_code'],30,23))
                p.setPen(QColor(PALETTE['text']));font=QFont('Segoe UI',10);font.setWeight(QFont.DemiBold);p.setFont(font);p.drawText(QRectF(x+53,y+9,width-65,22),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(title,Qt.ElideRight,int(width-65)))
                if subtitle:
                    p.setPen(QColor(PALETTE['muted']));p.setFont(QFont('Segoe UI',9));p.drawText(QRectF(x+53,y+31,width-65,20),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(subtitle,Qt.ElideRight,int(width-65)))
