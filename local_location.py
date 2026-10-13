"""Offline IP-country lookup. No HTTP, CDN or analytics calls."""
import ipaddress,json,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'assets'
COUNTRIES=json.loads((ROOT/'countries.json').read_text()) if (ROOT/'countries.json').exists() else {}
def country_info(code):return COUNTRIES.get(code.upper(),{})
def lookup_location(host):
    try:address=ipaddress.ip_address(host)
    except ValueError:
        # This resolves only the requested VPN endpoint, never a lookup service.
        records=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM);records.sort(key=lambda r:r[0]!=socket.AF_INET);address=ipaddress.ip_address(records[0][4][0])
    result={'ip':str(address),'country':'','country_code':'','city':''}
    if not address.is_global:return result
    import sqlite3
    with sqlite3.connect(f'file:{(ROOT/"ip-country.sqlite").as_posix()}?mode=ro&immutable=1',uri=True) as con:
        key=int(address).to_bytes(16,'big');row=con.execute(f'SELECT end,country FROM ipv{address.version} WHERE start<=? ORDER BY start DESC LIMIT 1',(key,)).fetchone()
    if row and key<=row[0]:result.update(country_code=row[1],country=country_info(row[1]).get('name',row[1]))
    return result
