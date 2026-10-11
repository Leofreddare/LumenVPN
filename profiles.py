"""Unlimited saved server metadata; authentication tokens stay in the OS vault."""
import json, os, uuid
from dataclasses import replace
from pathlib import Path
from core import Profile
from pairing import remember, recall, key_name

def metadata(profile,name=''):
    return {'id':uuid.uuid4().hex,'name':name or 'Private server','host':profile.host,'port':profile.port,'fingerprint':profile.validate(),'country':'','country_code':'','city':'','ip':'','favorite':False,'location_source':'unknown'}

def make_profile(item):
    # A placeholder validates metadata for vault key derivation; never used for connection.
    return Profile(item['host'],int(item['port']),'0'*32,item['fingerprint'])

class ProfileStore:
    def __init__(self,path):self.path=Path(path);self.items=[];self.selected=None;self.auto_location=True;self.secrets={};self.load()
    def load(self):
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('v')!=2:return
            self.auto_location=data.get('auto_location',True) is True
            for item in data.get('servers',[]):
                try:
                    p=make_profile(item);p.validate()
                    clean=metadata(p,str(item.get('name','Private server'))[:80]);clean['id']=str(item['id'])
                    for field in ['country','country_code','city','ip','location_source']:clean[field]=str(item.get(field,''))[:100]
                    clean['favorite']=item.get('favorite',False) is True
                    if self.get(clean['id']) is None:self.items.append(clean)
                except (ValueError,KeyError,TypeError):continue
            self.selected=data.get('selected') if self.get(data.get('selected')) else (self.items[0]['id'] if self.items else None)
        except (OSError,ValueError,TypeError,AttributeError):pass
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        safe=[{k:v for k,v in item.items() if k not in ('token','key','password')} for item in self.items]
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps({'v':2,'selected':self.selected,'auto_location':self.auto_location,'servers':safe},indent=2),encoding='utf-8');os.replace(temp,self.path)
    def get(self,ident):return next((i for i in self.items if i['id']==ident),None)
    def add(self,profile,name=''):
        pin=profile.validate();item=next((i for i in self.items if (i['host'],i['port'],i['fingerprint'])==(profile.host,profile.port,pin)),None)
        if item is None:item=metadata(profile,name);self.items.append(item)
        elif name:item['name']=name
        self.secrets[item['id']]=profile.token;saved=remember(profile) if getattr(self,'persist_new',True) else False
        self.selected=item['id'];self.save();return item,saved
    def replace_connection(self,ident,profile):
        item=self.get(ident)
        if item is None:raise ValueError('Server no longer exists.')
        pin=profile.validate()
        if any(other['id']!=ident and (other['host'],other['port'],other['fingerprint'])==(profile.host,profile.port,pin) for other in self.items):
            raise ValueError('That connection is already saved as another server.')
        old=make_profile(item);changed=item['host']!=profile.host
        saved=remember(profile) if getattr(self,'persist_new',True) else False;self.secrets[ident]=profile.token
        item.update(host=profile.host,port=profile.port,fingerprint=pin)
        if changed:
            item['ip']=''
            if item['location_source']!='manual':item.update(country='',country_code='',city='',location_source='unknown')
        self.save()
        if key_name(old)!=key_name(profile):
            try:
                import keyring
                keyring.delete_password('Lumen tunnel',key_name(old))
            except Exception:pass
        return saved
    def profile(self,ident=None):
        item=self.get(ident or self.selected)
        if item is None:return None
        p=make_profile(item);return replace(p,token=self.secrets.get(item['id']) or recall(p))
    def select(self,ident):
        if not self.get(ident):raise ValueError('Server no longer exists.')
        self.selected=ident;self.save()
    def remove(self,ident):
        item=self.get(ident)
        if not item:return
        try:
            import keyring
            keyring.delete_password('Lumen tunnel',key_name(make_profile(item)))
        except Exception:pass
        self.items.remove(item);self.secrets.pop(ident,None)
        if self.selected==ident:self.selected=self.items[0]['id'] if self.items else None
        self.save()
    def migrate(self,legacy):
        if self.items:return
        try:
            data=json.loads(Path(legacy).read_text());p=Profile(data['host'],data['port'],'0'*32,data['fingerprint']);token=recall(p)
            if token:self.add(replace(p,token=token))
        except (OSError,ValueError,KeyError):pass

from local_location import lookup_location
