"""padding-v1: bounded random TCP stream framing inside verified TLS."""
import asyncio,os,struct
MAX_DATA=32768
class PaddingReader:
    def __init__(self,reader):self.reader=reader;self.pending=b''
    async def read(self,n=65536):
        if n==0:return b''
        if not self.pending:
            try:header=await self.reader.readexactly(6)
            except asyncio.IncompleteReadError as e:
                if not e.partial:return b''
                raise
            size,pad=struct.unpack('!IH',header)
            if not 1<=size<=MAX_DATA or pad>63:raise ValueError('Invalid padding frame')
            self.pending=await self.reader.readexactly(size)
            if pad:await self.reader.readexactly(pad)
        size=len(self.pending) if n<0 else min(n,len(self.pending));data=self.pending[:size];self.pending=self.pending[size:];return data
    def __getattr__(self,name):return getattr(self.reader,name)
class PaddingWriter:
    def __init__(self,writer):self.writer=writer
    def write(self,data):
        for offset in range(0,len(data),MAX_DATA):
            part=data[offset:offset+MAX_DATA];padding=os.urandom(1)[0]&63
            self.writer.write(struct.pack('!IH',len(part),padding)+part+os.urandom(padding))
    def __getattr__(self,name):return getattr(self.writer,name)
