"""Validate an explicitly imported connection file; never fetch secrets publicly."""
import json
from pathlib import Path
from core import Profile

def load_connection(filename, local_port=1080):
    path=Path(filename)
    if path.stat().st_size>8192: raise ValueError('Connection file is too large.')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('v')!=1:
        raise ValueError('Not a supported Lumen connection file.')
    if any(not isinstance(data.get(k),str) for k in ['host','token','fingerprint']):
        raise ValueError('Connection file is missing required fields.')
    if type(data.get('port')) is not int:
        raise ValueError('Connection file has an invalid port.')
    profile=Profile(data['host'],data['port'],data['token'],data['fingerprint'],local_port)
    profile.validate()
    return profile

def key_name(profile):
    return f'{profile.host}:{profile.port}:{profile.validate()}'

def remember(profile):
    try:
        import keyring
        keyring.set_password('Lumen tunnel',key_name(profile),profile.token)
        # Detect null backends that claim success but discard the secret.
        return keyring.get_password('Lumen tunnel',key_name(profile))==profile.token
    except Exception:
        return False

def recall(profile):
    try:
        import keyring
        return keyring.get_password('Lumen tunnel',key_name(profile)) or ''
    except Exception:
        return ''
