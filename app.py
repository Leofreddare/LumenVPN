"""Polished grey Windows desktop client, with unlimited private relay profiles."""
import json, os, socket, sys, time, queue, threading
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QStandardPaths, QObject, QTimer, QSize
from PySide6.QtWidgets import QStackedWidget, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QDialog, QLineEdit, QScrollArea, QFrame, QFormLayout, QMenu, QSystemTrayIcon
from profile_types import Profile
from pairing import load_connection
from profiles import ProfileStore, lookup_location
from widgets import ActionButton, WorldMap, FadeLabel, SignalBars, QualityWidget, fast_pixmap, set_palette, icon, flag_pixmap, logo_icon
from preferences import Preferences,SettingsPage,DocumentationPage
from latency import LatencyScanner

class Worker(QThread):
    ready=Signal();failed=Signal(str);stats=Signal(int,int);endpoint=Signal(str);phase=Signal(str)
    def __init__(self,profile,options=None):super().__init__();self.profile=profile;self.options=options or {};self.loop=None;self.task=None;self.stopping=False
    def run(self):
        import asyncio
        if self.stopping:return
        self.loop=asyncio.new_event_loop();asyncio.set_event_loop(self.loop);self.task=self.loop.create_task(self.session())
        if self.stopping:self.task.cancel()
        try:self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:pass
        except Exception as error:
            if not self.stopping:self.failed.emit(str(error))
        finally:self.loop.close();self.loop=None
    async def session(self):
        import asyncio
        from core import choose_endpoint
        from windows_engine import WindowsEngine
        from native_transport import NativeTunnel
        if os.name!='nt':raise RuntimeError('Full-system mode is available on Windows x64.')
        # Resolve before installing routes; every transport uses the excluded address.
        addresses=await asyncio.wait_for(self.loop.getaddrinfo(self.profile.host,self.profile.port,type=socket.SOCK_STREAM),self.options.get('dial_timeout',15))
        family=self.options.get('address_family','Auto')
        if family!='Auto':addresses=[r for r in addresses if r[0]==(socket.AF_INET if family=='IPv4' else socket.AF_INET6)]
        if not addresses:raise RuntimeError('No server address matches your selected address family.')
        addresses.sort(key=lambda item:item[0]!=socket.AF_INET)
        self.phase.emit('Verifying your server…')
        endpoint,verified=await choose_endpoint(self.profile,[record[4][0] for record in addresses],options=self.options);self.endpoint.emit(endpoint)
        engine=WindowsEngine(self.options)
        tunnel=NativeTunnel(replace(self.profile,host=endpoint),verified.capabilities,options=engine.options)
        try:
            await tunnel.start();self.phase.emit("Preparing routing components…")
            # Shield startup so cancellation cannot leave an engine starting in a background thread.
            starting=asyncio.create_task(asyncio.to_thread(engine.start,endpoint,self.profile.local_port))
            try:await asyncio.shield(starting)
            except asyncio.CancelledError:
                try:await starting
                except Exception:pass
                raise
            self.ready.emit()
            while True:
                if engine.process.poll() is not None:raise RuntimeError('Windows adapter stopped. Reconnect to try again.')
                if engine.dns.process.poll() is not None:raise RuntimeError('The local DNS validator stopped. Reconnect to try again.')
                if tunnel.error:raise RuntimeError(tunnel.error)
                self.stats.emit(tunnel.upload,tunnel.download);await asyncio.sleep(self.options.get('stats_interval',1))
        finally:
            async def cleanup():
                try:await asyncio.to_thread(engine.stop)
                finally:await tunnel.stop()
            cleaning=asyncio.create_task(cleanup())
            try:await asyncio.shield(cleaning)
            except asyncio.CancelledError:await cleaning;raise
    def stop(self):
        if self.stopping:return
        self.stopping=True
        if self.loop and self.task:
            try:self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:pass # The finished signal can precede delivery to Qt.

STYLE='''
QWidget {background:#22252b;color:#e5e8ed;font-family:"Segoe UI";font-size:13px;}
QLabel {background:transparent;}
QLabel#brand {font-size:23px;font-weight:650;letter-spacing:1px;}
QLabel#muted {color:#959ba8;font-size:12px;}
QLabel#eyebrow {color:#858d9d;font-size:10px;letter-spacing:2px;font-weight:600;}
QLabel#locationTitle {font-size:25px;font-weight:600;}
QLabel#endpoint {font-size:20px;font-weight:550;letter-spacing:.3px;}
QLabel#metric {font-size:18px;font-weight:600;}
QLabel#pill {background:#333a46;border-radius:8px;padding:7px 10px;color:#c1cad8;font-size:11px;}
QFrame#rail {background:#191d25;border-right:1px solid #363d49;}
QFrame#sidebar {background:#252b35;border-right:1px solid #394250;}
QFrame#separator {background:#444e5e;}
QLabel#country {font-size:18px;font-weight:600;}
QLabel#badge {background:#3b414c;border:1px solid #505866;border-radius:13px;font-size:15px;font-weight:700;color:#dce1e9;}
QPushButton {background:#333842;border:1px solid #464d5a;border-radius:10px;padding:10px 14px;color:#e8ebf1;}
QPushButton:hover {background:#414856;border-color:#697384;} QPushButton:pressed {background:#272c35;} QPushButton:disabled {color:#727986;border-color:#363c46;}
QPushButton#iconButton {background:transparent;border:1px solid transparent;padding:6px;border-radius:9px;}
QPushButton#iconButton:hover {background:#373d47;border:1px solid #95a2b7;}
QPushButton#row {border:none;background:transparent;text-align:left;padding:0;}
QFrame#card {background:#2d323b;border:1px solid #414855;border-radius:14px;}
QFrame#serverRow {background:#2a313d;border:1px solid transparent;border-radius:9px;}
QFrame#serverRow[selected="true"] {background:#3b4555;border-color:#78869a;}
QFrame#serverRow:hover {border-color:#626e80;}
QLineEdit {background:#2d323b;border:1px solid #434b59;border-radius:10px;padding:11px 13px;selection-background-color:#65728a;}
QLineEdit:focus {border-color:#95a2b7;}
QScrollArea {border:none;background:transparent;} QScrollArea>QWidget>QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:6px;margin:3px;} QScrollBar::handle:vertical {background:#596272;border-radius:3px;min-height:28px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QCheckBox {spacing:10px;} QCheckBox::indicator {width:17px;height:17px;border:1px solid #778296;border-radius:5px;background:#2e343f;} QCheckBox::indicator:checked {background:#b6c3d6;}
'''
def label(text='',name=None):
    w=QLabel(text);w.setTextFormat(Qt.PlainText)
    if name:w.setObjectName(name)
    return w
def tool(kind,tip,callback):
    b=QPushButton();b.setObjectName('iconButton');b.setIcon(icon(kind));b.setIconSize(QSize(21,21));b.setFixedSize(34,34);b.setToolTip(tip);b.setAccessibleName(tip);b.clicked.connect(callback);return b

def size(n):return f'{n/1048576:.1f} MB' if n>=1048576 else f'{n/1024:.1f} KB' if n>=1024 else f'{n} B'

class GeoService(QObject):
    result=Signal(str,dict,str)
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=queue.Queue();self.pending=set();self.cache={};self.closed=False
        self.thread=None
    def submit(self,ident,host):
        if self.closed or ident in self.pending:return
        if self.thread is None:
            self.thread=threading.Thread(target=self.consume,daemon=True,name="Lumen locations");self.thread.start()
        self.pending.add(ident);self.jobs.put((ident,host))
    def consume(self):
        while True:
            item=self.jobs.get()
            if item is None:return
            if self.closed:continue
            ident,host=item
            try:
                data=self.cache.get(host) or lookup_location(host);self.cache[host]=data
                if not self.closed:self.result.emit(ident,data,'')
            except Exception:
                if not self.closed:self.result.emit(ident,{},'Country unavailable; edit location manually.')
    def close(self):self.closed=True;self.jobs.put(None)

class Window(QMainWindow):
    exitReady=Signal()
    def __init__(self,settings_path=None,tray_enabled=None):
        super().__init__();self.setWindowTitle('Lumen VPN');self.setWindowIcon(logo_icon());self.resize(966,670);self.setMinimumSize(880,610);self.setStyleSheet(STYLE);self.setAttribute(Qt.WA_DeleteOnClose)
        self.worker=None;self.profile=None;self.connected=False;self.busy=False;self.pending_server=None;self.active_server=None;self.started_at=0.
        self.quitting=False;self.tray=None;self.scanner=None;self.latencies={};self.latency_times={};self.quality_widgets={};self.rate_previous=None;self.recent_rates=None;self.waiting_fastest=False;self.retry_count=0;self.connection_failed=False;self.manual_disconnect=False
        self.preferences=Preferences((Path(settings_path).parent if settings_path else Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)))/'preferences.json');self.options=self.preferences.values;self.colors=self.preferences.theme()
        base=Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation));self.store=ProfileStore(settings_path or base/'servers.json');self.settings=self.store.path
        self.store.auto_location=self.options['offline_geolocation']
        self.geo=GeoService(self);self.geo.result.connect(self.geo_result)
        self.shell=QStackedWidget();self.setCentralWidget(self.shell);self.inner_page=None;root=QWidget();self.home=root;self.shell.addWidget(root);layout=QHBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        sidebar=QFrame();self.sidebar=sidebar;sidebar.setObjectName('sidebar');sidebar.setFixedWidth(342);left=QVBoxLayout(sidebar);left.setContentsMargins(18,21,18,17);left.setSpacing(16)
        self.status=FadeLabel('Disconnected', self);self.status.hide()
        self.caption=FadeLabel('');self.caption.setObjectName('muted');self.caption.setWordWrap(True);self.caption.hide()
        self.power=ActionButton();self.power.clicked.connect(self.toggle);# The primary CTA sits above the map, following the reference layout.
        self.action=label('CONNECT','eyebrow');self.action.hide()
        self.build_servers(left);layout.addWidget(sidebar)
        content=QWidget();right=QVBoxLayout(content);right.setContentsMargins(25,24,25,20);right.setSpacing(12)
        self.stack=QStackedWidget();right.addWidget(self.stack,1);self.build_home()
        self.duration=label('');self.duration.hide();layout.addWidget(content,1)
        self.clock=QTimer(self);self.clock.setInterval(1000);self.clock.timeout.connect(self.update_clock);self.clock.start();self.update_server();self.refresh_servers()
        if (os.name=='nt' if tray_enabled is None else tray_enabled) and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray=QSystemTrayIcon(logo_icon(),self);menu=QMenu(self)
            menu.addAction('Open Lumen VPN',self.show_main);self.tray_connect=menu.addAction('Connect',self.toggle)
            menu.addAction('Preferences',self.show_settings);menu.addSeparator();menu.addAction('Exit',self.request_exit)
            self.tray.setContextMenu(menu);self.tray.activated.connect(self.tray_activated);self.update_tray();self.tray.show()
        self.probe_timer=QTimer(self);self.probe_timer.timeout.connect(self.scan_latency);self.apply_preferences()
        self.retry_timer=QTimer(self);self.retry_timer.setSingleShot(True);self.retry_timer.timeout.connect(self.retry_connection)
        if settings_path is None:
            QTimer.singleShot(600,self.startup_actions)
    def server_sort_key(self,item):
        favourite=not item['favorite'] if self.options['favorites_first'] else False
        sort=self.options['sort'];value=self.latencies.get(item['id'])
        key=(value if value is not None else float('inf')) if sort=='Latency' else (item['name'] if sort=='Name' else item['country'] or item['name']).casefold()
        return favourite,key,item['name'].casefold()
    @staticmethod
    def literal_ip(host):
        import ipaddress
        try:ipaddress.ip_address(host);return True
        except ValueError:return False
    def scan_latency(self,force=False):
        if self.quitting or self.worker or self.scanner or (not force and not self.options['auto_probe']):return
        items=[]
        for item in self.store.items:
            if self.waiting_fastest and self.options['fastest_favorites'] and not item['favorite']:continue
            profile=self.store.profile(item['id'])
            if profile and profile.token and (self.options['probe_hostnames'] or self.literal_ip(profile.host)):items.append((item['id'],profile))
        if not items:
            if self.waiting_fastest:self.waiting_fastest=False;self.fast_button.setText('Fastest VPN');self.power.set_mode('idle');self.update_connect_caption();self.refresh_servers();self.notify('Import connection files with credentials before measuring locations.')
            return
        self.scanner=LatencyScanner(items,self.options['probe_timeout'],self,concurrency=self.options['probe_concurrency']);self.scanner.measured.connect(self.latency_result);self.scanner.finished.connect(self.scanner_finished);self.scanner.start()
    def latency_result(self,ident,value):
        if self.worker or self.quitting:return
        if self.store.get(ident):self.latencies[ident]=value;self.latency_times[ident]=time.monotonic();self.refresh_servers()
    def quality_tip(self,ident):
        value=self.latencies.get(ident);age=int(time.monotonic()-self.latency_times.get(ident,time.monotonic()))
        text=(f'Authenticated response: {value:.0f} ms ({age}s ago)' if value is not None else 'Not measured or unreachable')+'\nBars estimate latency quality; bandwidth capacity has not been tested.'
        if self.options['show_session_speed'] and self.connected and ident==self.active_server and self.recent_rates:
            up,down=self.recent_rates;text+=f'\nRecent traffic: ↑ {up:.2f} Mbps · ↓ {down:.2f} Mbps\nActual traffic rate, not maximum capacity.'
        return text
    def scanner_finished(self):
        scanner=self.scanner;self.scanner=None
        if scanner:scanner.deleteLater()
        if self.quitting:self.close();return
        if self.waiting_fastest:
            self.waiting_fastest=False;self.fast_button.setText('Fastest VPN');self.refresh_servers();self.choose_fastest()
    def choose_fastest(self):
        available=[i for i in self.store.items if (not self.options['fastest_favorites'] or i['favorite']) and self.latencies.get(i['id']) is not None and time.monotonic()-self.latency_times.get(i['id'],0)<=self.options['probe_interval']*2]
        if not available:self.power.set_mode('idle');self.update_connect_caption();self.notify('No measured location is reachable. You can still select one manually.');return
        self.connect_location(min(available,key=lambda i:self.latencies[i['id']])['id'])
    def connect_fastest(self):
        if self.busy or self.quitting:return
        if any((not self.options['fastest_favorites'] or i['favorite']) and self.latencies.get(i['id']) is not None and time.monotonic()-self.latency_times.get(i['id'],0)<=self.options['probe_interval'] for i in self.store.items):self.choose_fastest();return
        if self.worker:self.notify('Disconnect first to measure the other locations.');return
        self.waiting_fastest=True;self.power.set_mode('connecting');self.fast_button.setText('Measuring…');self.fast_button.setEnabled(False);self.scan_latency(force=True)
    def retry_connection(self):
        if not self.quitting and not self.worker and not self.manual_disconnect:self.toggle()
    def startup_actions(self):
        if self.quitting:return
        if self.options['start_minimized'] and self.tray:self.hide()
        if self.options['auto_connect']:
            if self.options['default_fastest']:self.connect_fastest()
            elif self.store.selected:self.toggle()
        elif self.options['auto_probe']:self.scan_latency()
    def open_page(self,page):
        if not self.show_home():page.deleteLater();return
        self.inner_page=page;page.back.connect(self.show_home);self.shell.addWidget(page);self.shell.setCurrentWidget(page)
        for button in page.findChildren(QPushButton):
            kind=button.property('iconKind')
            if kind:button.setIcon(icon(kind,self.colors['button_text'] if button.property('buttonInk') else self.colors['text']))
        page.back_button.setIcon(icon('chevron-left'))
    def show_home(self):
        if isinstance(self.inner_page,SettingsPage):
            if not self.inner_page.confirm_leave():return False
            self.options=self.preferences.values;self.apply_preferences()
        self.shell.setCurrentWidget(self.home)
        if self.inner_page:
            page=self.inner_page;self.inner_page=None;self.shell.removeWidget(page);page.hide();page.deleteLater()
        return True
    def show_settings(self):
        page=SettingsPage(self.preferences,self);page.saved.connect(self.settings_saved);page.previewChanged.connect(self.preview_preferences);self.open_page(page)
    def settings_saved(self):
        self.options=self.preferences.values;self.apply_preferences();self.show_home()
    def show_documentation(self):self.open_page(DocumentationPage(self))
    def preview_preferences(self,values):
        committed=self.options;self.options=values
        try:self.apply_preferences(preview=True)
        finally:self.options=committed
    def apply_preferences(self,preview=False):
        from preferences import THEMES,DEFAULT_THEME
        colors=self.options.get('custom_theme',{}).get('colors',DEFAULT_THEME) if self.options['theme']=='Custom' else THEMES[self.options['theme']];self.colors=colors;set_palette(colors,self.options['flag_radius'])
        roles={'#22252b':'background','#252b35':'sidebar','#191d25':'sidebar','#2d323b':'surface','#2a313d':'surface','#333842':'surface','#2c323d':'surface','#e5e8ed':'text','#e8ebf1':'text','#959ba8':'muted','#858d9d':'muted','#434b59':'border','#414855':'border','#394250':'border','#363d49':'border','#444e5e':'border','#464d5a':'border','#3b4555':'selected','#414856':'selected','#373d47':'selected','#78869a':'accent','#95a2b7':'accent','#697384':'accent','#626e80':'accent'}
        roles.update({'#272c35':'selected','#333a46':'surface','#3b414c':'surface','#2e343f':'surface','#505866':'border','#363c46':'border','#778296':'border','#596272':'muted','#727986':'muted','#c1cad8':'text','#dce1e9':'text','#65728a':'accent','#b6c3d6':'accent'})
        import re
        styled=re.sub(r'#[0-9a-fA-F]{6}',lambda m:colors.get(roles.get(m.group(),''),m.group()),STYLE)
        styled=styled.replace('font-size:13px;',f"font-size:{self.options['font_size']}px;")
        styled+=' QMenu, QDialog {background:'+colors['background']+';} QMenu::item:selected, QListWidget::item:selected {background:'+colors['selected']+';} QComboBox,QSpinBox,QTextBrowser,QListWidget {background:'+colors['surface']+';color:'+colors['text']+';border:1px solid '+colors['border']+';border-radius:7px;padding:7px;} QToolTip {background:'+colors['surface']+';color:'+colors['text']+';border:1px solid '+colors['border']+';}'
        icons_path=(Path(__file__).parent/'assets/icons').resolve().as_posix()
        styled+=f' QCheckBox::indicator:checked {{image:url("{icons_path}/check.svg");}} QSpinBox::up-arrow {{image:url("{icons_path}/arrow-up.svg");width:10px;height:10px;}} QSpinBox::down-arrow {{image:url("{icons_path}/arrow-down.svg");width:10px;height:10px;}}'
        styled+=f"""
QLabel#pageHeading {{font-size:24px;font-weight:600;}}
QLabel#sectionHeading {{font-size:22px;font-weight:600;margin-bottom:5px;}}
QLabel#optionTitle {{font-weight:600;}}
QLabel#optionHint {{font-size:11px;color:{colors['muted']};}}
QFrame#preferenceRow {{background:{colors['surface']};border:1px solid {colors['border']};border-radius:12px;}}
QPushButton#categoryButton {{background:transparent;border:none;text-align:left;padding:10px 12px;border-radius:9px;}}
QPushButton#categoryButton:hover {{background:{colors['surface']};}}
QPushButton#categoryButton:checked {{background:{colors['selected']};color:{colors['text']};font-weight:600;}}
QPushButton#stepButton {{padding:0;border-radius:7px;font-size:17px;}}
QPushButton#themeChoice {{padding:9px 8px;font-size:11px;}}
QPushButton#quietButton {{background:transparent;border:1px solid transparent;color:{colors['muted']};}}
QPushButton#quietButton:hover {{background:{colors['surface']};}}
QPushButton#saveButton {{background:{colors['button']};color:{colors['button_text']};border-color:{colors['button']};font-weight:600;}}
QComboBox {{padding:8px 32px 8px 12px;min-height:22px;}}
QComboBox::drop-down {{border:none;width:30px;}}
QComboBox::down-arrow {{image:none;width:0px;height:0px;}}
QComboBox QAbstractItemView {{background:{colors['surface']};color:{colors['text']};selection-background-color:{colors['selected']};selection-color:{colors['text']};border:1px solid {colors['border']};padding:6px;}}
QLabel#groupHeading {{font-size:12px;font-weight:600;color:{colors['muted']};}}
QSpinBox {{padding:8px 4px;}}
QTextBrowser#localDocument {{background:transparent;border:none;padding:0;}}
QWidget#categoryRail {{background:transparent;}}
QWidget#numberControl {{background:transparent;}}
QWidget#statColumn {{background:transparent;}}
"""
        if not self.options['hover_glow']:styled+=' QPushButton#iconButton:hover {border:1px solid transparent;background:transparent;}'
        if self.inner_page:
            self.inner_page.nav_area.setFixedWidth(205+max(0,self.options['font_size']-13)*8)
            for button in self.inner_page.findChildren(QPushButton):
                kind=button.property('iconKind')
                if kind:button.setIcon(icon(kind,colors['button_text'] if button.property('buttonInk') else colors['text']))
            self.inner_page.back_button.setIcon(icon('chevron-left'))
        self.setStyleSheet(styled);self.sidebar.setFixedWidth(self.options['sidebar_width']);self.setMinimumWidth(self.options['sidebar_width']+540)
        self.map.setVisible(self.options['show_map']);self.map.tooltips_enabled=self.options['map_tooltips'];self.map.motion=self.options['animations'];self.map.pulse=self.options['map_pulse'];self.map._land_key=None;self.map.set_mode(self.map.mode)
        duration=self.options['animation_ms'] if self.options['animations'] else 0
        self.power.motion=self.options['animations'];self.power.blend_animation.setDuration(duration);self.power.hover_animation.setDuration(min(duration,160));self.power.timer.setInterval(round(1000/int(self.options['animation_fps'])));self.power.set_mode(self.power.mode);self.map.move_animation.setDuration(duration);self.map.timer.setInterval(round(1000/int(self.options['animation_fps'])))
        self.status.anim.setDuration(duration);self.caption.anim.setDuration(duration)
        if not preview:
            self.store.auto_location=self.options['offline_geolocation'];self.store.persist_new=self.options['remember_new_tokens'];self.probe_timer.setInterval(self.options['probe_interval']*1000)
            if self.options['auto_probe']:self.probe_timer.start()
            else:
                self.probe_timer.stop()
                if self.scanner and not self.waiting_fastest:self.scanner.stop()
        for kind,symbol in self.stat_icons:symbol.setPixmap(icon(kind,colors['muted']).pixmap(15,15))
        self.search_action.setIcon(icon('search',colors['muted']));self.add_button.setIcon(icon('plus'));self.fast_badge.setPixmap(fast_pixmap());self.settings_button.setIcon(icon('gear'));self.docs_button.setIcon(icon('book'));self.update_server();self.refresh_servers();self.map.update()

    def show_main(self):
        self.showNormal();self.raise_();self.activateWindow()
    def tray_activated(self,reason):
        if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick):self.show_main()
    def update_tray(self):
        if not self.tray:return
        state='Disconnecting' if self.worker and self.worker.stopping else 'Connected' if self.connected else 'Connecting' if self.worker else 'Disconnected'
        item=self.store.get(self.active_server);location=(' · '+item['country']) if item and self.connected and self.options['show_tray_location'] else '';self.tray.setToolTip('Lumen VPN · '+state+location)
        self.tray_connect.setText('Disconnect' if self.worker else 'Connect')
        self.tray_connect.setEnabled(not self.quitting and bool(self.store.items) and not (self.worker and self.worker.stopping))
    def request_exit(self):
        if self.quitting:return
        if isinstance(self.inner_page,SettingsPage) and not self.show_home():return
        self.quitting=True;self.pending_server=None;self.retry_timer.stop();self.waiting_fastest=False
        if self.worker:self.begin_disconnect()
        else:self.close()
    def build_home(self):
        home=QWidget();box=QVBoxLayout(home);box.setContentsMargins(0,0,0,0);box.setSpacing(8)
        header=QHBoxLayout();self.badge=label();self.badge.setAlignment(Qt.AlignCenter);self.badge.setFixedSize(45,45);header.addWidget(self.badge);header.addSpacing(6)
        headings=QVBoxLayout();headings.setSpacing(3);self.country=label('Your private network','country');self.country.setObjectName('locationTitle');self.city=label('Add a server to get started','muted');headings.addWidget(self.country);headings.addWidget(self.city);header.addLayout(headings,1)
        shortcuts=QVBoxLayout();shortcuts.setSpacing(2);self.settings_button=tool('gear','Preferences',self.show_settings);self.docs_button=tool('book','Help',self.show_documentation);shortcuts.addWidget(self.settings_button);shortcuts.addWidget(self.docs_button);header.addLayout(shortcuts);box.addLayout(header)
        box.addSpacing(10);box.addWidget(self.power,alignment=Qt.AlignCenter)
        self.map=WorldMap();self.map.locationClicked.connect(self.select_map_location);self.map.emptyClicked.connect(self.deselect_map);box.addWidget(self.map,1)
        self.card=QFrame();self.card.setObjectName('card');card=QVBoxLayout(self.card);card.setContentsMargins(18,16,18,16);card.setSpacing(13)
        self.server=label('No server selected','endpoint');card.addWidget(self.server)
        separator=QFrame();self.stats_separator=separator;separator.setObjectName('separator');separator.setFixedHeight(1);card.addWidget(separator)
        stats=QHBoxLayout();stats.setSpacing(24);self.total_widgets=[];self.sent=label('0 B','metric');self.received=label('0 B','metric');self.stat_icons=[]
        for kind,title,value in [('up','Uploaded',self.sent),('down','Downloaded',self.received),('transport','Transport',label('TLS 1.3','metric'))]:
            holder=QWidget();holder.setObjectName('statColumn');column=QVBoxLayout(holder);column.setContentsMargins(0,0,0,0);column.setSpacing(8)
            heading=QHBoxLayout();heading.setSpacing(6);heading.setContentsMargins(0,0,0,0);symbol=label();symbol.setFixedSize(15,15);symbol.setPixmap(icon(kind,'#a4b0c2').pixmap(15,15));self.stat_icons.append((kind,symbol));heading.addWidget(symbol);heading.addWidget(label(title,'muted'));heading.addStretch();column.addLayout(heading);column.addWidget(value);column.addStretch();stats.addWidget(holder,1)
            if kind!='transport':self.total_widgets.append(holder)
        card.addLayout(stats);box.addWidget(self.card);self.traffic=label('')
        self.stack.addWidget(home)
    def build_servers(self,box):
        self.search=QLineEdit();self.search.setPlaceholderText('Search servers');self.search_action=self.search.addAction(icon('search','#8b95a8'),QLineEdit.LeadingPosition);self.search.textChanged.connect(self.refresh_servers);box.addWidget(self.search)
        fastest=QFrame();fastest.setObjectName('serverRow');row=QHBoxLayout(fastest);row.setContentsMargins(10,12,10,12);self.fast_badge=label();self.fast_badge.setPixmap(fast_pixmap());self.fast_badge.setFixedSize(37,37);row.addWidget(self.fast_badge)
        self.fast_button=QPushButton('Fastest VPN');self.fast_button.setObjectName('row');self.fast_button.setMinimumHeight(43);self.fast_button.setCursor(Qt.PointingHandCursor);self.fast_button.clicked.connect(self.connect_fastest);self.fast_button.setToolTip('Connect to the saved location with the lowest measured response latency.');row.addWidget(self.fast_button,1);box.addWidget(fastest)
        self.count=label('');self.count.hide()
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.rows_widget=QWidget();self.rows=QVBoxLayout(self.rows_widget);self.rows.setContentsMargins(0,0,1,0);self.rows.setSpacing(5);self.scroll.setWidget(self.rows_widget);box.addWidget(self.scroll,1)
        self.add_button=QPushButton('Add VPN connections');self.add_button.setIcon(icon('plus'));self.add_button.clicked.connect(self.import_connections);box.addWidget(self.add_button)
    def show_servers(self):self.refresh_servers();self.search.setFocus()
    def notify(self,message):
        if message:QMessageBox.warning(self,'Lumen VPN',message)
    def update_connect_caption(self):
        item=self.store.get(self.store.selected)
        text='Connect to fastest VPN'
        if item:
            name=item['name'].strip();defaults={'private server','client-connection',item['host'].casefold(),str(item.get('ip','')).casefold(),f"{item['host']}:{item['port']}".casefold()}
            target=(item['country'] or 'VPN') if self.options['redact_server_names'] or name.casefold() in defaults else (name or item['country'] or 'VPN')
            text='Connect to '+target
        self.power.set_caption(text)
    def update_server(self):
        item=self.store.get(self.store.selected);self.profile=self.store.profile()
        map_items=[dict(i,name='') for i in self.store.items] if self.options['redact_server_names'] else self.store.items
        self.map.set_locations(map_items);self.map.select_server(item['id'] if item else None)
        if item:
            self.badge.setPixmap(flag_pixmap(item.get('country_code',''),44,33));self.country.setText(item.get('country') or 'Country unknown')
            name=item['name'] if not self.options['redact_server_names'] and item['name'].casefold()!='private server' and item['name']!=item['host'] else ''
            subtitle=' · '.join(dict.fromkeys(x for x in [item.get('city') if self.options['show_city'] else '',name] if x))
            self.city.setText(self.city.fontMetrics().elidedText(subtitle,Qt.ElideRight,260));self.city.setVisible(bool(subtitle))
        else:self.badge.setPixmap(flag_pixmap('',44,33));self.country.setText('Select a VPN' if self.store.items else 'Add a VPN server');self.city.setText('' if self.store.items else 'Import a connection to get started');self.city.setVisible(not self.store.items)
        active=self.store.get(self.active_server) if self.connected else None
        display=active or item
        if display:
            ip=display.get('ip') or display['host'];address=f'[{ip}]' if ':' in ip else ip;self.server.setText('••••••••' if self.options['mask_endpoint'] else self.server.fontMetrics().elidedText(f'{address}:{display["port"]}',Qt.ElideMiddle,260))
        else:self.server.setText('')
        self.update_connect_caption()
        if not self.busy:self.power.setEnabled(True)
        self.server.setToolTip('');self.card.setVisible(self.connected);self.server.setVisible(self.options['show_endpoint']);self.stats_separator.setVisible(self.options['show_endpoint'])
        for widget in self.total_widgets:widget.setVisible(self.options['show_transfer_totals'])
    def refresh_servers(self,*args):
        self.quality_widgets={}
        position=self.scroll.verticalScrollBar().value()
        while self.rows.count():
            entry=self.rows.takeAt(0)
            if entry.widget():entry.widget().hide();entry.widget().deleteLater()
        query=self.search.text().strip().casefold();items=sorted(self.store.items,key=self.server_sort_key)
        visible=[i for i in items if (not query or query in ' '.join(str(i.get(k,'')) for k in ['name','country','city','ip','host']).casefold())]
        self.count.setText(f'{len(self.store.items)} saved server'+('' if len(self.store.items)==1 else 's'))
        for item in visible:
            ident=item['id'];frame=QFrame();frame.setObjectName('serverRow');frame.setProperty('selected',ident==self.store.selected);row=QHBoxLayout(frame);row.setContentsMargins(10,self.options['row_padding'],5,self.options['row_padding']);row.setSpacing(5)
            badge=label();badge.setPixmap(flag_pixmap(item['country_code'],36,27));badge.setFixedSize(37,37);badge.setAlignment(Qt.AlignCenter);row.addWidget(badge)
            choose=QPushButton();choose.setObjectName('row');choose.setCursor(Qt.PointingHandCursor);choose.setMinimumHeight(53)
            title=item['country'] or 'Country unknown';safe_name=item['name'] if not self.options['redact_server_names'] and item['name'] not in (item['host'],item.get('ip'),f'{item["host"]}:{item["port"]}') else 'Private server';sub=' · '.join(dict.fromkeys(x for x in [item['city'] if self.options['show_city'] else '',safe_name] if x and x!=title and x.casefold()!='private server'));ip=item['ip'] or item['host'];metrics=choose.fontMetrics()
            choose.setText('\n'.join(metrics.elidedText(t,Qt.ElideMiddle,108) for t in [title,sub] if t));choose.setToolTip(f'{safe_name}\n{title}');choose.clicked.connect(lambda checked=False,i=ident:self.select_server(i));choose.setEnabled(not self.busy);row.addWidget(choose,1)
            quality=QualityWidget(lambda ident=ident:self.quality_tip(ident));quality_layout=QVBoxLayout(quality);quality_layout.setContentsMargins(0,0,0,0);quality_layout.setSpacing(1);quality_layout.setAlignment(Qt.AlignCenter);rtt=self.latencies.get(ident);bars=SignalBars(rtt,self.options['good_latency'],self.options['medium_latency']);quality_layout.addWidget(bars,alignment=Qt.AlignCenter)
            if self.options['show_latency']:
                rtt_text=label(f'{rtt:.0f} ms' if rtt is not None else '—','muted');rtt_text.setStyleSheet('font-size:9px;');quality_layout.addWidget(rtt_text,alignment=Qt.AlignCenter)
            quality.setToolTip(self.quality_tip(ident));self.quality_widgets[ident]=quality;row.addWidget(quality)
            star=tool('star','Remove favourite' if item['favorite'] else 'Favourite server',lambda checked=False,i=ident:self.favorite_server(i));star.setIcon(icon('star-filled' if item['favorite'] else 'star','#ffffff' if item['favorite'] and self.options['theme']!='Light' else self.colors['text'] if item['favorite'] else self.colors['muted']));star.setProperty('favorite',item['favorite']);row.addWidget(star)
            menu_button=tool('more','Server options',lambda checked=False,i=ident:self.server_menu(i));row.addWidget(menu_button);self.rows.addWidget(frame)
            for target in [frame,badge,choose,quality,star,menu_button,*quality.findChildren(QWidget)]:
                target.setContextMenuPolicy(Qt.CustomContextMenu);target.customContextMenuRequested.connect(lambda pos,i=ident:self.server_menu(i))
        if not visible:
            empty=label('No matching servers' if self.store.items else 'Your private servers live here.\n\nImport connection files to add them.','muted');empty.setAlignment(Qt.AlignCenter);empty.setMinimumHeight(150);self.rows.addWidget(empty)
        self.rows.addStretch();self.scroll.verticalScrollBar().setValue(position)
        self.fast_button.setEnabled(bool(self.store.items) and not self.busy and not self.waiting_fastest);self.update_tray()
    def server_menu(self,ident):
        menu=QMenu(self);menu.setStyleSheet('QMenu {padding:6px;} QMenu::item {padding:9px 18px;}')
        menu.addAction(icon('edit'),'Edit VPN',lambda:self.edit_server(ident))
        item=self.store.get(ident)
        menu.addAction(icon('star'),'Remove favourite' if item and item['favorite'] else 'Favourite server',lambda:self.favorite_server(ident))
        remove=menu.addAction(icon('trash'),'Remove server',lambda:self.remove_server(ident));remove.setEnabled(ident!=self.active_server)
        from PySide6.QtGui import QCursor
        menu.exec(QCursor.pos());menu.deleteLater()
    def import_connections(self):
        files,_=QFileDialog.getOpenFileNames(self,'Add VPN connections','','Connection files (*.json)')
        if files:self.add_files(files)
    def add_files(self,files):
        selected=self.store.selected;added=[];errors=[];temporary=False
        for filename in files:
            try:
                profile=load_connection(filename);item,saved=self.store.add(profile,Path(filename).stem if Path(filename).stem!='client-connection' else 'Private server');temporary|=not saved
                location=json.loads(Path(filename).read_text(encoding='utf-8'))
                if isinstance(location.get('country_code'),str) and len(location['country_code'])==2:
                    from local_location import country_info
                    code=location['country_code'].upper();info=country_info(code);item.update(country=location.get('country') or info.get('name',''),country_code=code,city=str(location.get('city',''))[:80],location_source='manual');self.store.save()
                added.append(item)
            except Exception as error:errors.append(f'{Path(filename).name}: {error}')
        if self.worker and selected:self.store.select(selected)
        self.update_server();self.refresh_servers()
        if added and temporary:self.notify('Credentials are available for this session only; reimport on next launch.')
        if errors:self.notify('\n'.join(errors)[:600])
        if self.options['auto_probe'] and not self.worker:QTimer.singleShot(100,self.scan_latency)
        if self.store.auto_location:
            for item in added:
                if item['location_source']!='manual':self.geo.submit(item['id'],item['host'])
    def geo_result(self,ident,data,error):
        self.geo.pending.discard(ident);item=self.store.get(ident)
        if not item or item['location_source']=='manual' or not self.store.auto_location:return
        if data:
            if ident==self.active_server and item['ip'] and data.get('ip')!=item['ip']:
                self.geo.submit(ident,item['ip']);return
            item.update(data);item['location_source']='lookup';self.store.save();self.update_server();self.refresh_servers()
        elif error:
            item['location_source']='unavailable';self.store.save()
            if ident==self.store.selected:self.city.setToolTip(error)
    def favorite_server(self,ident):
        item=self.store.get(ident)
        if item:item['favorite']=not item['favorite'];self.store.save();self.refresh_servers()
    def select_server(self,ident):
        if self.busy:return
        if self.worker and ident!=self.active_server:
            self.pending_server=ident;self.begin_disconnect();self.stack.setCurrentIndex(0);return
        self.store.select(ident);self.update_server();self.refresh_servers();self.stack.setCurrentIndex(0)
    def remove_server(self,ident):
        if ident==self.active_server:return
        self.store.remove(ident);self.update_server();self.refresh_servers()
    def reimport_connection(self,ident,filename):
        if ident==self.active_server:raise ValueError('Disconnect this VPN before replacing its connection file.')
        profile=load_connection(filename);saved=self.store.replace_connection(ident,profile)
        self.latencies.pop(ident,None);self.latency_times.pop(ident,None)
        self.update_server();self.refresh_servers()
        item=self.store.get(ident)
        if item['location_source']!='manual':self.geo.submit(ident,profile.host)
        if not saved:self.notify('Connection updated for this session. Credential storage is unavailable; reimport next time.')
        return saved
    def edit_server(self,ident):
        item=self.store.get(ident)
        if not item:return
        dialog=QDialog(self);dialog.setWindowTitle('Edit VPN');dialog.setMinimumWidth(370);form=QFormLayout(dialog);form.setContentsMargins(20,20,20,20);form.setSpacing(12)
        fields={}
        for key,title in [('name','Name'),('country','Country'),('country_code','Country code'),('city','City')]:
            fields[key]=QLineEdit(item[key]);fields[key].setMaxLength(2 if key=='country_code' else 80);form.addRow(title,fields[key])
        form.addRow('Server',label(f'{item["host"]}:{item["port"]}','muted'));form.addRow('Resolved IP',label(item['ip'] or 'Not resolved yet','muted'))
        reimport=QPushButton('Reimport connection file');reimport.setIcon(icon('plus'));reimport.setEnabled(ident!=self.active_server);reimport.setToolTip('Disconnect this VPN first.' if ident==self.active_server else 'Replace this VPN’s connection credentials while keeping its name and favourite status.');form.addRow(reimport)
        def choose_connection():
            filename,_=QFileDialog.getOpenFileName(dialog,'Reimport connection file','','Connection files (*.json)')
            if not filename:return
            try:self.reimport_connection(ident,filename);dialog.accept()
            except Exception as error:QMessageBox.warning(dialog,'Could not reimport',str(error))
        reimport.clicked.connect(choose_connection)
        buttons=QHBoxLayout();save=QPushButton('Save');buttons.addWidget(save);form.addRow(buttons)
        def save_details():
            code=fields['country_code'].text().strip().upper()
            if code and (len(code)!=2 or not code.isascii() or not code.isalpha()):self.notify('Use a two-letter country code, such as GB or IS.');return
            for key,field in fields.items():item[key]=field.text().strip()
            item['country_code']=code;item['name']=item['name'] or item['host'];item['location_source']='manual';self.store.save();self.update_server();self.refresh_servers();dialog.accept()
        save.clicked.connect(save_details);dialog.exec()
    def select_map_location(self,ident):
        if self.busy or not self.store.get(ident):return
        self.store.select(ident);self.update_server();self.refresh_servers()
    def deselect_map(self):
        if self.busy:return
        self.store.selected=None;self.store.save();self.update_server();self.refresh_servers()
    def connect_location(self,ident):
        if self.busy or not self.store.get(ident):return
        if self.worker:
            if ident!=self.active_server:self.select_server(ident)
            return
        self.store.select(ident);self.update_server();self.refresh_servers();self.toggle()
    def toggle(self):
        if self.quitting:return
        if self.waiting_fastest:
            self.waiting_fastest=False;self.fast_button.setText('Fastest VPN');self.power.set_mode('idle');self.update_connect_caption()
            if self.scanner:self.scanner.stop()
            self.refresh_servers();return
        self.waiting_fastest=False;self.fast_button.setText('Fastest VPN')
        if self.worker:self.manual_disconnect=True;self.retry_timer.stop();self.pending_server=None;self.begin_disconnect();return
        if not self.store.selected:
            if self.store.items:self.connect_fastest()
            else:self.show_servers();self.import_connections()
            return
        self.retry_timer.stop();self.manual_disconnect=False;self.connection_failed=False
        if self.scanner:self.scanner.stop()
        self.profile=self.store.profile()
        if self.profile:self.profile=replace(self.profile,local_port=self.options['local_port'])
        if not self.profile or not self.profile.token:self.notify('Reimport this server’s connection file to restore its credentials.');self.show_servers();return
        self.notify('');self.busy=True;self.active_server=self.store.selected;self.status.transition('Connecting…');self.caption.transition('Verifying your private server');self.action.setText('CANCEL');self.power.set_mode('connecting');self.map.set_mode('connecting')
        self.worker=Worker(self.profile,dict(self.options));self.worker.ready.connect(self.on_ready);self.worker.failed.connect(self.on_error);self.worker.stats.connect(self.on_stats);self.worker.endpoint.connect(self.resolved_endpoint);self.worker.phase.connect(self.caption.transition);self.worker.finished.connect(self.on_finished);self.worker.start();self.refresh_servers();self.update_tray()
    def resolved_endpoint(self,endpoint):
        item=self.store.get(self.active_server)
        if item:
            previous=item['ip'];item['ip']=endpoint
            if previous!=endpoint and item['location_source']!='manual':
                item.update(country='',country_code='',city='',location_source='unknown')
            self.store.save();self.update_server()
            if self.store.auto_location and item['location_source']!='manual' and (previous!=endpoint or not item['country']):self.geo.submit(item['id'],endpoint)
    def begin_disconnect(self):
        if not self.worker:return
        self.card.hide();self.busy=True;self.status.transition('Switching…' if self.pending_server else 'Disconnecting…');self.caption.transition('Restoring Windows routes');self.action.setText('PLEASE WAIT');self.power.set_mode('disconnecting');self.map.set_mode('disconnecting');self.power.setEnabled(False);self.worker.stop();self.refresh_servers();self.update_tray()
    def on_ready(self):
        if self.worker and self.worker.stopping:return
        self.retry_count=0;self.busy=False;self.connected=True;self.started_at=time.monotonic();self.status.transition('Connected');self.caption.transition('Windows traffic uses your private server');self.action.setText('DISCONNECT');self.power.set_mode('connected');self.map.set_mode('connected');self.update_clock();self.update_server();self.refresh_servers()
        if self.options['minimize_on_connect'] and self.tray:self.hide()
    def on_error(self,message):
        if self.quitting or self.manual_disconnect:return
        self.connection_failed=True;self.pending_server=None
        if not self.options['auto_reconnect']:self.notify(message)
    def on_finished(self):
        worker=self.worker;self.worker=None;self.busy=False;self.connected=False;self.active_server=None;self.status.transition('Disconnected');self.caption.transition('Connect to your private server');self.action.setText('CONNECT');self.power.setEnabled(True);self.power.set_mode('idle');self.map.set_mode('idle');self.duration.setText('');self.refresh_servers()
        if self.options['clear_latency_on_disconnect']:self.latencies.clear();self.latency_times.clear();self.refresh_servers()
        self.update_server();self.started_at=0.;self.rate_previous=None;self.recent_rates=None;self.reset_stats();self.update_tray()
        if worker:worker.deleteLater()
        if self.quitting:self.close();return
        pending=self.pending_server;self.pending_server=None
        if pending and self.store.get(pending):self.store.select(pending);self.update_server();QTimer.singleShot(0,self.toggle)
        elif self.connection_failed and self.options['auto_reconnect'] and not self.manual_disconnect:
            if self.retry_count<self.options['reconnect_attempts']:
                self.retry_count+=1;self.retry_timer.start(self.options['reconnect_delay']*1000)
            else:self.notify('Automatic reconnect attempts exhausted. Connect again to retry.');self.retry_count=0
    def format_size(self,n):
        result=size(n)
        return result.replace('MB','MiB').replace('KB','KiB') if self.options['statistics_units']=='MiB / KiB' else result
    def on_stats(self,up,down):
        if self.connected:
            self.sent.setText(self.format_size(up));self.received.setText(self.format_size(down));self.traffic.setText(f'{self.format_size(up)} sent · {self.format_size(down)} received')
            now=time.monotonic();quality=self.quality_widgets.get(self.active_server)
            if self.rate_previous and quality:
                previous,old_up,old_down=self.rate_previous;elapsed=max(.001,now-previous)
                self.recent_rates=(max(0,up-old_up)*8/elapsed/1e6,max(0,down-old_down)*8/elapsed/1e6);quality.setToolTip(self.quality_tip(self.active_server))
            self.rate_previous=(now,up,down)
    def reset_stats(self):self.sent.setText('0 B');self.received.setText('0 B');self.traffic.setText('0 B sent · 0 B received')
    def update_clock(self):
        if self.connected:
            seconds=int(time.monotonic()-self.started_at);self.duration.setText(f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}')
    def closeEvent(self,event):
        if not self.quitting and self.options['close_to_tray'] and self.tray and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore();self.hide();return
        if not self.quitting and isinstance(self.inner_page,SettingsPage) and not self.show_home():event.ignore();return
        self.pending_server=None
        if self.worker:
            event.ignore();self.request_exit();return
        self.quitting=True;self.retry_timer.stop();self.probe_timer.stop()
        if self.scanner:
            event.ignore();self.scanner.stop();return
        self.geo.close();self.clock.stop();self.map.timer.stop();self.map.move_animation.stop();self.power.timer.stop();self.power.blend_animation.stop();self.power.hover_animation.stop();self.status.anim.stop();self.caption.anim.stop()
        if self.tray:self.tray.hide()
        event.accept();self.exitReady.emit()
def main():
    if os.name=='nt':
        import ctypes,subprocess
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Lumen.VPN')
        if not ctypes.windll.shell32.IsUserAnAdmin():
            pythonw=Path(sys.executable).with_name('pythonw.exe');executable=str(pythonw) if pythonw.exists() else sys.executable
            result=ctypes.windll.shell32.ShellExecuteW(None,'runas',executable,subprocess.list2cmdline([str(Path(__file__).with_name('app.pyw').resolve())]),str(Path(__file__).resolve().parent),1)
            if result<=32:
                ctypes.windll.user32.MessageBoxW(None,'Administrator permission is needed for the Windows VPN adapter.','Lumen',0x10)
                sys.exit(1)
            sys.exit(0)
    app=QApplication(sys.argv);app.setOrganizationName('Lumen');app.setApplicationName('Lumen');window=Window();app.setQuitOnLastWindowClosed(window.tray is None);window.exitReady.connect(app.quit);window.show();sys.exit(app.exec())
