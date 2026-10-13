"""Lightweight connection metadata; no networking modules at UI startup."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Profile:
    host: str
    port: int
    token: str
    fingerprint: str
    local_port: int = 1080
    def validate(self):
        if not self.host.strip() or any(c in self.host for c in '/\\ \n\r'):
            raise ValueError('Enter a hostname or IP without a URL prefix.')
        if not (1 <= self.port <= 65535 and 1024 <= self.local_port <= 65535):
            raise ValueError('Invalid server or local port.')
        if not 32 <= len(self.token) <= 512:
            raise ValueError('Import your server connection file first.')
        pin=self.fingerprint.replace(':','').replace(' ','').lower()
        if len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):
            raise ValueError('Import the certificate fingerprint from your trusted server panel.')
        return pin

