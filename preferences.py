"""Local, validated preferences and data-only themes. No executable theme content."""
import ipaddress,json,re,os
from pathlib import Path
from PySide6.QtWidgets import QHBoxLayout,QVBoxLayout,QStackedWidget,QScrollArea,QWidget,QCheckBox,QComboBox,QLineEdit,QPushButton,QLabel,QFileDialog,QMessageBox,QTextBrowser,QFrame,QSizePolicy

DEFAULT_THEME={'background':'#22252b','sidebar':'#252b35','surface':'#2d323b','border':'#414855','text':'#e5e8ed','muted':'#959ba8','accent':'#ccd9ec','button':'#ccd0d7','button_text':'#24272f','map':'#303743','selected':'#3b4555','good':'#43c89e','medium':'#efa858','bad':'#ed737d'}
THEMES={'Graphite':DEFAULT_THEME,'Midnight':dict(DEFAULT_THEME,background='#131820',sidebar='#18202b',surface='#202b38',border='#344354',accent='#91bddc',map='#263342',selected='#33495e'), 'Ocean':dict(DEFAULT_THEME,background='#15272d',sidebar='#19323b',surface='#233f49',border='#395660',accent='#83dbc8',map='#2b4650',selected='#315c66',button='#9bded2',button_text='#112a2b'), 'Light':dict(DEFAULT_THEME,background='#f5f6f8',sidebar='#e9edf2',surface='#ffffff',border='#c8ced8',text='#222936',muted='#596777',accent='#496885',button='#d6e2ef',button_text='#1c3248',map='#d3dce6',selected='#dbe6f2',good='#187b59',medium='#97620a',bad='#b33747')}
# key, label, kind, value bounds / choices, category
FIELDS=[
 ('theme','Colour theme','choice',list(THEMES)+['Custom'],'Appearance'),
 ('font_size','Text size','int',(11,17),'Appearance'),
 ('sidebar_width','Server list width','int',(330,420),'Appearance'),
 ('row_padding','Server row spacing','int',(6,18),'Appearance'),
 ('flag_radius','Flag corner radius','int',(0,12),'Appearance'),
 ('show_map','Show map','bool',None,'Appearance'),
 ('map_tooltips','Map hover cards','bool',None,'Appearance'),
 ('animations','Enable animations','bool',None,'Motion'),
 ('animation_ms','Transition duration (ms)','int',(100,800),'Motion'),
 ('animation_fps','Animation frame rate','choice',['20','30','60'],'Motion'),
 ('map_pulse','Animate active map marker','bool',None,'Motion'),
 ('close_to_tray','Close window to tray','bool',None,'General'),
 ('start_minimized','Start in notification area','bool',None,'General'),
 ('auto_connect','Connect when app opens','bool',None,'General'),
 ('default_fastest','Use fastest VPN on startup','bool',None,'General'),
 ('auto_reconnect','Reconnect after connection failure','bool',None,'Connection'),
 ('reconnect_delay','Retry delay (seconds)','int',(2,60),'Connection'),
 ('reconnect_attempts','Maximum retry attempts','int',(1,10),'Connection'),
 ('local_port','Local SOCKS port','int',(1024,65535),'Connection'),
 ('warm_connections','Prepare two TLS connections','bool',None,'Connection'),
 ('mtu','Tunnel MTU','int',(1280,1500),'Network'),
 ('dns_server','Encrypted DNS resolver IP','ip',None,'Network'),
 ('dns_name','DNS certificate hostname','hostname',None,'Network'),
 ('stream_buffer','Stream buffer size','choice',['Auto','64 KiB','128 KiB','256 KiB'],'Network'),
 ('stats_interval','Statistics update interval (seconds)','int',(1,5),'Network'),
 ('auto_probe','Measure server latency automatically','bool',None,'Server list'),
 ('probe_interval','Latency refresh interval (seconds)','int',(30,600),'Server list'),
 ('probe_timeout','Probe timeout (seconds)','int',(2,10),'Server list'),
 ('good_latency','Green latency limit (ms)','int',(10,300),'Server list'),
 ('medium_latency','Orange latency limit (ms)','int',(20,1000),'Server list'),
 ('show_latency','Show latency numbers','bool',None,'Server list'),
 ('sort','Sort locations by','choice',['Country','Name','Latency'],'Server list'),
 ('favorites_first','Put favourites first','bool',None,'Server list'),
 ('offline_geolocation','Look up countries locally','bool',None,'Privacy'),
 ('statistics_units','Data units','choice',['MB / KB','MiB / KiB'],'Privacy'),
]
DEFAULTS=dict(theme='Graphite',font_size=13,sidebar_width=342,row_padding=10,flag_radius=4,show_map=True,map_tooltips=True,animations=True,animation_ms=350,animation_fps='60',map_pulse=True,close_to_tray=True,start_minimized=False,auto_connect=False,default_fastest=False,auto_reconnect=False,reconnect_delay=5,reconnect_attempts=3,local_port=1080,warm_connections=True,mtu=1400,dns_server='1.1.1.1',dns_name='cloudflare-dns.com',stream_buffer='Auto',stats_interval=1,auto_probe=True,probe_interval=120,probe_timeout=4,good_latency=80,medium_latency=180,show_latency=True,sort='Country',favorites_first=True,offline_geolocation=True,statistics_units='MB / KB')

EXTRA_FIELDS=[('show_city', 'Show city', 'bool', None, 'Appearance', True, 'Display city names in location previews.'), ('hover_glow', 'Highlight icon buttons on hover', 'bool', None, 'Appearance', True, 'Add a soft border and background to hovered icons.'), ('minimize_on_connect', 'Minimise after connecting', 'bool', None, 'General', False, 'Hide in the notification area after a successful connection.'), ('address_family', 'Server address family', 'choice', ['Auto', 'IPv4', 'IPv6'], 'Connection', 'Auto', 'Choose which resolved server addresses can be used.'), ('dial_timeout', 'TLS connection timeout (seconds)', 'int', (3, 30), 'Connection', 15, 'Time allowed to open an encrypted server connection.'), ('request_timeout', 'Relay request timeout (seconds)', 'int', (2, 30), 'Connection', 15, 'Time allowed for the server to authenticate a request.'), ('tcp_keepalive', 'TCP keepalive interval (seconds)', 'int', (0, 120), 'Connection', 30, 'OS keepalive interval; zero disables keepalive probes.'), ('session_resumption', 'Resume TLS sessions', 'bool', None, 'Connection', True, 'Reuse in-memory TLS tickets while still checking the pinned identity.'), ('warm_count', 'Prepared connection count', 'int', (1, 2), 'Connection', 2, 'Maximum prepared links when preparation is enabled.'), ('warm_lifetime', 'Prepared link lifetime (seconds)', 'int', (5, 20), 'Connection', 20, 'Discard unused prepared links after this time.'), ('warm_retry', 'Preparation retry delay (seconds)', 'int', (1, 30), 'Connection', 5, 'Back off after an unsuccessful preparation attempt.'), ('max_connections', 'Concurrent connection limit', 'int', (8, 128), 'Network', 128, 'Bound concurrent local TCP and UDP associations.'), ('idle_timeout', 'Idle stream timeout (seconds)', 'int', (30, 900), 'Network', 300, 'Close inactive client streams; the worker may enforce a shorter limit.'), ('udp_queue_packets', 'UDP queue packet limit', 'int', (16, 128), 'Network', 128, 'Bound queued datagrams; fixed byte budgets also apply.'), ('udp_batch_packets', 'UDP write batch limit', 'int', (1, 32), 'Network', 32, 'Batch already queued packets without waiting for more.'), ('dns_port', 'Encrypted DNS port', 'int', (1, 65535), 'Network', 853, 'DNS-over-TLS port on your configured resolver.'), ('allow_udp', 'Allow UDP traffic', 'bool', None, 'Privacy', True, 'Block tunneled UDP when disabled. Some apps may stop working.'), ('block_ipv6', 'Block tunneled IPv6 traffic', 'bool', None, 'Privacy', False, 'Reject IPv6 application traffic inside the tunnel; keep IPv6 capture routes.'), ('show_endpoint', 'Show connected VPN address', 'bool', None, 'Privacy', True, 'Display the active server address only while connected.'), ('mask_endpoint', 'Mask connected VPN address', 'bool', None, 'Privacy', False, 'Replace the displayed address with bullets.'), ('show_transfer_totals', 'Show transfer totals', 'bool', None, 'Privacy', True, 'Display uploaded and downloaded session totals.'), ('show_session_speed', 'Show recent speed in latency tooltip', 'bool', None, 'Privacy', True, 'Display actual current traffic rate for the connected VPN.'), ('remember_new_tokens', 'Save new tokens to Windows vault', 'bool', None, 'Privacy', True, 'Save future imported tokens when the vault is available. Existing entries remain.'), ('clear_latency_on_disconnect', 'Clear latency after disconnecting', 'bool', None, 'Privacy', False, 'Forget in-memory latency and measurement ages on disconnect.'), ('redact_server_names', 'Hide custom server names', 'bool', None, 'Privacy', False, 'Show country and city instead of custom names in previews and the list.'), ('probe_hostnames', 'Resolve hostnames for latency checks', 'bool', None, 'Privacy', True, 'When disabled, measure only servers saved with literal IP addresses.'), ('show_tray_location', 'Show location in tray tooltip', 'bool', None, 'Privacy', False, 'Include the active country in the notification-area tooltip.'), ('probe_concurrency', 'Parallel latency checks', 'int', (1, 4), 'Server list', 2, 'Limit simultaneous checks against your saved servers.'), ('fastest_favorites', 'Fastest VPN uses favourites only', 'bool', None, 'Server list', False, 'Restrict the shortcut to starred locations.')]
EXTRA_FIELDS.append(('tun_stack','Windows network stack','choice',['Mixed','System','gVisor'],'Network','Mixed','Mixed is the default. Test System for CPU use or gVisor for compatibility; reconnect to apply.'))
FIELDS.extend((k,l,t,b,c) for k,l,t,b,c,v,d in EXTRA_FIELDS)
DEFAULTS.update({k:v for k,l,t,b,c,v,d in EXTRA_FIELDS})

def validate_theme(data):
    if not isinstance(data,dict) or data.get('v')!=1:raise ValueError('Use a version 1 Lumen theme JSON file.')
    if set(data)-{'v','name','colors'}:raise ValueError('Theme contains unsupported fields.')
    name=data.get('name','Custom')
    if not isinstance(name,str) or not 1<=len(name)<=60:raise ValueError('Theme name must have 1–60 characters.')
    colors=data.get('colors')
    if not isinstance(colors,dict) or not colors or set(colors)-set(DEFAULT_THEME):raise ValueError('Use only documented colour keys.')
    if any(not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in colors.values()):raise ValueError('Colours must use #RRGGBB format.')
    return {'v':1,'name':name,'colors':dict(DEFAULT_THEME,**colors)}

def validate_settings(data):
    result=dict(DEFAULTS)
    for key,_,kind,bounds,_ in FIELDS:
        value=data.get(key,DEFAULTS[key])
        if kind=='bool':
            if type(value)!=bool:raise ValueError(f'{key} must be true or false.')
        elif kind=='int':
            if type(value)!=int or not bounds[0]<=value<=bounds[1]:raise ValueError(f'{key} is outside its allowed range.')
        elif kind=='choice':
            if value not in bounds:raise ValueError(f'Invalid {key}.')
        elif kind=='ip':ipaddress.ip_address(value)
        elif kind=='hostname':
            if not isinstance(value,str) or len(value)>253 or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',value):raise ValueError('Enter a DNS certificate hostname, without a URL.')
        result[key]=value
    if result['medium_latency']<=result['good_latency']:raise ValueError('Orange latency limit must be higher than green.')
    if data.get('custom_theme'):result['custom_theme']=validate_theme(data['custom_theme'])
    if result['theme']=='Custom' and not result.get('custom_theme'):raise ValueError('Import a custom theme first.')
    return result

class Preferences:
    def __init__(self,path):
        self.path=Path(path);self.values=dict(DEFAULTS)
        try:self.values=validate_settings(json.loads(self.path.read_text()))
        except (OSError,ValueError,TypeError,AttributeError):pass
    def save(self,data):
        values=validate_settings(data);self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(values,indent=2));os.replace(temp,self.path);self.values=values
    def theme(self):return self.values.get('custom_theme',{}).get('colors',DEFAULT_THEME) if self.values['theme']=='Custom' else THEMES[self.values['theme']]

from PySide6.QtCore import Qt,Signal,QSize,QByteArray
from PySide6.QtGui import QPainter,QColor,QPixmap,QIcon,QIntValidator,QPen,QTextCursor,QTextTable,QTextLength
from widgets import icon
import widgets

DESCRIPTIONS={
 'theme':'Choose a built-in palette or import your own.', 'font_size':'Size of the main interface text.', 'sidebar_width':'Give your location names more room.', 'row_padding':'Space above and below each saved location.', 'flag_radius':'Round flag corners throughout the app.', 'show_map':'Display the interactive location map.', 'map_tooltips':'Show country, flag and name above a map pin.',
 'animations':'Smooth transitions and connection indicators.', 'animation_ms':'How quickly interface states change.', 'animation_fps':'Target frame rate while animations are active.', 'map_pulse':'A subtle halo around the active location.',
 'close_to_tray':'Keep the VPN running when you close the window.', 'start_minimized':'Open in the Windows notification area.', 'auto_connect':'Connect to a saved location when Lumen opens.', 'default_fastest':'Choose the lowest-latency location on startup.',
 'auto_reconnect':'Try again after an unexpected connection failure.', 'reconnect_delay':'Wait between automatic connection attempts.', 'reconnect_attempts':'Limit consecutive unsuccessful attempts.', 'local_port':'Loopback SOCKS listener; avoid ports already in use.', 'warm_connections':'Prepare up to two links to reduce connection delay.',
 'mtu':'Packet size for the Windows tunnel adapter.', 'dns_server':'Public resolver supporting DNS-over-TLS on port 853.', 'dns_name':'TLS certificate hostname for your DNS resolver.', 'stream_buffer':'Auto adapts to available CPU and memory.', 'stats_interval':'How often transferred data totals update.',
 'auto_probe':'Check only your saved servers while disconnected.', 'probe_interval':'Time between background latency checks.', 'probe_timeout':'Stop waiting for a slow or unreachable location.', 'good_latency':'Three green bars at or below this value.', 'medium_latency':'Two orange bars at or below this value.', 'show_latency':'Display milliseconds next to the signal bars.', 'sort':'Choose how saved locations are ordered.', 'favorites_first':'Keep starred locations above the others.',
 'offline_geolocation':'Use the bundled country database, without web requests.', 'statistics_units':'Choose traditional labels or explicit binary units.'
}
DESCRIPTIONS.update({k:d for k,l,t,b,c,v,d in EXTRA_FIELDS})
CATEGORY_NAMES={'Appearance':'Appearance','Motion':'Animations','General':'App behaviour','Connection':'Connections','Network':'Traffic and DNS','Server list':'VPN locations','Privacy':'Privacy and data'}
CATEGORY_ICONS={'Appearance':'palette','Motion':'activity','General':'monitor','Connection':'plug','Network':'globe','Server list':'list','Privacy':'lock'}
SECTIONS={
 'Appearance':[('Theme',['theme']),('Layout',['font_size','sidebar_width','row_padding','flag_radius']),('Location display',['show_map','map_tooltips','show_city']),('Buttons',['hover_glow'])],
 'Motion':[('Transitions',['animations','animation_ms','animation_fps']),('Map animation',['map_pulse'])],
 'General':[('Window',['close_to_tray','start_minimized','minimize_on_connect']),('Startup connection',['auto_connect','default_fastest'])],
 'Connection':[('Automatic reconnect',['auto_reconnect','reconnect_delay','reconnect_attempts']),('Server connection',['address_family','dial_timeout','request_timeout','tcp_keepalive','session_resumption','local_port']),('Prepared connections',['warm_connections','warm_count','warm_lifetime','warm_retry'])],
 'Network':[('Encrypted DNS',['dns_server','dns_name','dns_port']),('Tunnel and streams',['tun_stack','mtu','stream_buffer','max_connections','idle_timeout']),('UDP queues',['udp_queue_packets','udp_batch_packets']),('Statistics',['stats_interval'])],
 'Server list':[('Latency checks',['auto_probe','probe_interval','probe_timeout','probe_concurrency']),('Signal indicators',['good_latency','medium_latency','show_latency']),('Sorting and selection',['sort','favorites_first','fastest_favorites'])],
 'Privacy':[('Traffic restrictions',['allow_udp','block_ipv6']),('Credential storage',['remember_new_tokens']),('Location and measurements',['offline_geolocation','probe_hostnames','clear_latency_on_disconnect']),('On-screen privacy',['show_endpoint','mask_endpoint','redact_server_names','show_tray_location']),('Session statistics',['show_transfer_totals','show_session_speed','statistics_units'])]
}

class ThemedComboBox(QComboBox):
    """Draw a local chevron in the current palette, independent of native styles."""
    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(widgets.PALETTE['text'] if self.isEnabled() else widgets.PALETTE['muted']),1.7,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        x=self.width()-18;y=self.height()/2;painter.drawLine(int(x-4),int(y-2),int(x),int(y+2));painter.drawLine(int(x),int(y+2),int(x+4),int(y-2))

class Toggle(QCheckBox):
    def __init__(self,parent=None):super().__init__(parent);self.setFixedSize(42,24);self.setCursor(Qt.PointingHandCursor)
    def hitButton(self,point):return self.rect().contains(point)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);colors=widgets.PALETTE;p.setPen(Qt.NoPen);p.setBrush(QColor(colors['accent'] if self.isChecked() else colors['border']));p.drawRoundedRect(0,2,42,20,10,10);p.setBrush(QColor(colors['background'] if self.isChecked() else colors['text']));p.drawEllipse(24 if self.isChecked() else 4,5,14,14)
        if self.hasFocus():p.setPen(QColor(colors['text']));p.setBrush(Qt.NoBrush);p.drawRoundedRect(0,0,41,23,11,11)

class NumberInput(QLineEdit):
    def __init__(self):super().__init__();self.low=0;self.high=2147483647;self.setAlignment(Qt.AlignCenter);self.setFixedSize(70,36);self.setStyleSheet('padding:4px;')
    def setRange(self,low,high):self.low=low;self.high=high;self.setValidator(QIntValidator(low,high,self))
    def value(self):return int(self.text())
    def setValue(self,value):self.setText(str(max(self.low,min(self.high,value))))
    def step(self,amount):
        try:value=self.value()
        except ValueError:value=self.low
        self.setValue(value+amount)
    def stepDown(self):self.step(-1)
    def stepUp(self):self.step(1)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Up,Qt.Key_Down):self.step(1 if event.key()==Qt.Key_Up else -1);event.accept()
        else:super().keyPressEvent(event)

class Page(QWidget):
    back=Signal()
    def __init__(self,title,subtitle,parent=None):
        super().__init__(parent);self.setObjectName('preferencesPage');root=QVBoxLayout(self);root.setContentsMargins(24,20,24,20);root.setSpacing(20)
        header=QHBoxLayout();self.back_button=QPushButton();self.back_button.setIcon(icon('chevron-left'));self.back_button.setFixedSize(36,36);self.back_button.setToolTip('Back to VPN');self.back_button.setAccessibleName('Back to VPN');self.back_button.clicked.connect(lambda checked=False:self.back.emit());header.addWidget(self.back_button);header.addSpacing(12)
        titles=QVBoxLayout();titles.setSpacing(3);heading=QLabel(title);heading.setObjectName('pageHeading');hint=QLabel(subtitle);hint.setObjectName('muted');titles.addWidget(heading);
        if subtitle:titles.addWidget(hint)
        header.addLayout(titles,1);root.addLayout(header)
        body=QHBoxLayout();body.setSpacing(24);self.navigation=QVBoxLayout();self.navigation.setContentsMargins(0,0,0,0);self.navigation.setSpacing(4);nav_widget=QWidget();nav_widget.setObjectName('categoryRail');nav_widget.setLayout(self.navigation);nav_area=QScrollArea();self.nav_area=nav_area;nav_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);nav_area.setWidgetResizable(True);nav_area.setFixedWidth(205);nav_area.setWidget(nav_widget);body.addWidget(nav_area);self.stack=QStackedWidget();body.addWidget(self.stack,1);root.addLayout(body,1);self.root=root;self.buttons=[]
    def add_category(self,title,widget,kind='book'):
        index=self.stack.count();self.stack.addWidget(widget);button=QPushButton(title);button.setObjectName('categoryButton');button.setProperty('iconKind',kind);button.setIcon(icon(kind));button.setIconSize(QSize(18,18));button.setCheckable(True);button.setMinimumHeight(40);button.clicked.connect(lambda checked=False,i=index:self.select_category(i));self.navigation.addWidget(button);self.buttons.append(button)
    def select_category(self,index):
        self.stack.setCurrentIndex(index)
        for i,button in enumerate(self.buttons):button.setChecked(i==index)
    def finish_navigation(self):self.navigation.addStretch();self.select_category(0)

class SettingsPage(Page):
    saved=Signal();previewChanged=Signal(dict)
    def __init__(self,preferences,parent=None):
        super().__init__('Preferences','',parent);self.preferences=preferences;self.custom=preferences.values.get('custom_theme');self.fields={}
        for category in dict.fromkeys(f[4] for f in FIELDS):
            area=QScrollArea();area.setWidgetResizable(True);page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(0,0,12,18);layout.setSpacing(0)
            heading=QLabel(CATEGORY_NAMES[category]);heading.setObjectName('sectionHeading');layout.addWidget(heading);layout.addSpacing(14)
            entries={field[0]:field for field in FIELDS if field[4]==category};sections=SECTIONS[category]
            for key in [key for _,keys in sections for key in keys]:
                key,title,kind,bounds,group=entries[key]
                section=next(name for name,keys in sections if key in keys)
                if key==next(keys[0] for name,keys in sections if name==section):
                    if key!=sections[0][1][0]:layout.addSpacing(20)
                    subheading=QLabel(section);subheading.setObjectName('groupHeading');layout.addWidget(subheading);layout.addSpacing(10)
                row=QFrame();row.setObjectName('preferenceRow');line=QHBoxLayout(row);line.setContentsMargins(16,14,16,14);line.setSpacing(24);labels=QVBoxLayout();labels.setSpacing(4);caption=QLabel(title);caption.setObjectName('optionTitle');caption.setWordWrap(True);detail=QLabel(DESCRIPTIONS[key]);detail.setObjectName('optionHint');detail.setWordWrap(True);labels.addWidget(caption);labels.addWidget(detail);line.addLayout(labels,1)
                if kind=='bool':field=Toggle();field.setChecked(preferences.values[key]);control=field
                elif kind=='int':
                    field=NumberInput();field.setRange(*bounds);field.setValue(preferences.values[key]);control=QWidget();control.setObjectName('numberControl');controls=QHBoxLayout(control);controls.setContentsMargins(0,0,0,0);controls.setSpacing(5)
                    minus=QPushButton('−');plus=QPushButton('+');minus.setObjectName('stepButton');plus.setObjectName('stepButton');minus.setFixedSize(28,30);plus.setFixedSize(28,30);minus.setAccessibleName('Decrease '+title);plus.setAccessibleName('Increase '+title);minus.clicked.connect(field.stepDown);plus.clicked.connect(field.stepUp);controls.addWidget(minus);controls.addWidget(field);controls.addWidget(plus)
                elif kind=='choice':field=ThemedComboBox();field.addItems(bounds);field.setCurrentText(preferences.values[key]);field.setFixedSize(185,40);control=field
                else:field=QLineEdit(preferences.values[key]);field.setFixedSize(190,40);control=field
                field.setAccessibleName(title);
                if kind=='int':field.setToolTip(f'{bounds[0]}–{bounds[1]}')
                self.fields[key]=field;line.addWidget(control,0,Qt.AlignVCenter);layout.addWidget(row);layout.addSpacing(8)
                if key=='theme':
                    buttons=QHBoxLayout();buttons.setContentsMargins(0,4,0,0);buttons.setSpacing(12);import_button=QPushButton('Import theme');export_button=QPushButton('Export theme')
                    for button,kind in [(import_button,'import'),(export_button,'export')]:button.setIcon(icon(kind));button.setProperty('iconKind',kind);button.setMinimumHeight(40);buttons.addWidget(button)
                    buttons.addStretch();layout.addLayout(buttons);import_button.clicked.connect(self.import_theme);export_button.clicked.connect(self.export_theme)
            layout.addStretch();area.setWidget(page);self.add_category(CATEGORY_NAMES[category],area,CATEGORY_ICONS[category])
        self.finish_navigation();footer=QHBoxLayout();footer.setSpacing(6);reset=QPushButton('Reset defaults');reset.setObjectName('quietButton');reset.setIcon(icon('reset'));reset.setProperty('iconKind','reset');footer.addWidget(reset);footer.addStretch();discard=QPushButton('Discard');save=QPushButton('Save changes');save.setObjectName('saveButton');save.setIcon(icon('check',widgets.PALETTE['button_text']));save.setProperty('iconKind','check');save.setProperty('buttonInk',True);discard.setIcon(icon('x'));discard.setProperty('iconKind','x');footer.addWidget(discard);footer.addWidget(save);self.root.addLayout(footer);reset.clicked.connect(self.reset);discard.clicked.connect(self.discard);save.clicked.connect(self.save)
        self.baseline=self.collect_raw()
        for key,_,kind,_,_ in FIELDS:
            field=self.fields[key];signal=field.toggled if kind=='bool' else field.currentTextChanged if kind=='choice' else field.textChanged;signal.connect(self.preview)
    def collect_raw(self):
        return {k:(w.isChecked() if isinstance(w,Toggle) else w.currentText() if isinstance(w,QComboBox) else w.text()) for k,w in self.fields.items()}|{'custom_theme':self.custom}
    def dirty(self):return self.collect_raw()!=self.baseline
    def preview(self,*args):
        try:self.previewChanged.emit(self.collect())
        except (ValueError,TypeError):pass
    def discard(self):
        self.baseline=self.collect_raw();self.back.emit()
    def confirm_leave(self):
        if not self.dirty():return True
        choice=QMessageBox.question(self,'Unsaved changes','You have unsaved changes.',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Cancel)
        if choice==QMessageBox.Cancel:return False
        if choice==QMessageBox.Save:
            try:self.preferences.save(self.collect());self.baseline=self.collect_raw()
            except (ValueError,OSError) as error:QMessageBox.warning(self,'Settings',str(error));return False
        return True
    def collect(self):
        values={}
        for key,_,kind,_,_ in FIELDS:
            w=self.fields[key];values[key]=w.isChecked() if kind=='bool' else w.value() if kind=='int' else w.currentText() if kind=='choice' else w.text().strip()
        if self.custom:values['custom_theme']=self.custom
        return validate_settings(values)
    def save(self):
        try:self.preferences.save(self.collect());self.baseline=self.collect_raw();self.saved.emit();return True
        except (ValueError,OSError) as error:QMessageBox.warning(self,'Settings',str(error))
    def reset(self):
        for key,_,kind,_,_ in FIELDS:
            w=self.fields[key];value=DEFAULTS[key]
            if kind=='bool':w.setChecked(value)
            elif kind=='int':w.setValue(value)
            elif kind=='choice':w.setCurrentText(value)
            else:w.setText(value)
    def import_theme(self):
        path,_=QFileDialog.getOpenFileName(self,'Import Lumen theme','','Theme JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>16384:raise ValueError('Theme file is too large.')
            self.custom=validate_theme(json.loads(Path(path).read_text(encoding='utf-8')));self.fields['theme'].setCurrentText('Custom');self.preview()
        except (OSError,ValueError,TypeError) as error:QMessageBox.warning(self,'Theme',str(error))
    def export_theme(self):
        path,_=QFileDialog.getSaveFileName(self,'Export Lumen theme','lumen-theme.json','Theme JSON (*.json)')
        if not path:return
        try:
            choice=self.fields['theme'].currentText();theme=self.custom if choice=='Custom' else dict(v=1,name=choice,colors=THEMES[choice]);Path(path).write_text(json.dumps(theme,indent=2))
        except (OSError,KeyError) as error:QMessageBox.warning(self,'Theme',str(error))


class LocalDocument(QTextBrowser):
    def setMarkdown(self,text):
        super().setMarkdown(text)
        block=self.document().begin()
        while block.isValid():
            cursor=QTextCursor(block);format=block.blockFormat();heading=format.headingLevel();format.setTopMargin(16 if heading>1 else 0);format.setBottomMargin(20 if heading==1 else 8 if block.textList() else 14);cursor.setBlockFormat(format);block=block.next()
        for frame in self.document().rootFrame().childFrames():
            if isinstance(frame,QTextTable):
                format=frame.format();format.setCellPadding(8);format.setCellSpacing(0);format.setBorder(.7);format.setBorderBrush(QColor(widgets.PALETTE['border']));format.setWidth(QTextLength(QTextLength.PercentageLength,100));frame.setFormat(format)
    def __init__(self,parent=None):super().__init__(parent);self.setOpenExternalLinks(False);self.setOpenLinks(False);self.setObjectName('localDocument')
    def loadResource(self,kind,url):
        # Documentation uses text only. Never resolve remote or local image URLs.
        return QByteArray()

def documentation_sections(text):
    sections=[];title=None;lines=[]
    for line in text.splitlines():
        if line.startswith('## ') or line.startswith('### '):
            if title:sections.append((title,'\n'.join(lines).strip()))
            title=line.split(' ',1)[1];lines=[]
        elif title:lines.append(line)
    if title:sections.append((title,'\n'.join(lines).strip()))
    return sections

class DocumentationPage(Page):
    def __init__(self,parent=None):
        super().__init__('Help','',parent);self.sections=documentation_sections((Path(__file__).parent/'DOCUMENTATION.md').read_text(encoding='utf-8'));self.browsers=[]
        names={'Connect, switch and close':'Getting started','Fastest VPN and signal bars':'Choosing a VPN','Preferences':'Preferences overview','General':'App behaviour','Appearance':'Appearance','Motion':'Animations','Connection':'Connections','Network':'Traffic and DNS','Server list':'VPN locations','Privacy':'Privacy and data','Creating themes':'Custom themes','Hosting and security limits':'Server hosting','Troubleshooting':'Troubleshooting','Interface references':'Credits','Performance':'Performance'}
        symbols=['power','map-pin','sliders','monitor','palette','activity','plug','globe','list','lock','paintbrush','cloud','wrench','gauge','book']
        for index,(title,text) in enumerate(self.sections):
            browser=LocalDocument();self.browsers.append(browser);browser.document().setDocumentMargin(14);browser.document().setDefaultStyleSheet('p {margin-top:0px;margin-bottom:16px;} h1 {font-size:24px;margin-bottom:22px;} h2 {font-size:17px;margin-top:20px;margin-bottom:10px;} li {margin-bottom:9px;} th,td {padding:9px 12px;} pre {margin-top:16px;margin-bottom:16px;}')
            browser.setMarkdown('# '+names.get(title,title)+'\n\n'+text);self.add_category(names.get(title,title),browser,symbols[index%len(symbols)])
        self.finish_navigation()
