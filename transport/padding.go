// padding-v1: bounded random padding INSIDE authenticated TLS, not custom encryption.
package main

import (
	"crypto/rand"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"sync"
)

const padPayload = 32768

var padPool = sync.Pool{New: func() any { return make([]byte, padPayload+69) }}

type paddedConn struct {
	net.Conn
	reader    io.Reader
	remaining int
	skip      int
	writeMu   sync.Mutex
}

func (c *paddedConn) Read(out []byte) (int, error) {
	if len(out) == 0 {
		return 0, nil
	}
	if c.remaining == 0 {
		if c.skip > 0 {
			if _, e := io.CopyN(io.Discard, c.reader, int64(c.skip)); e != nil {
				return 0, e
			}
			c.skip = 0
		}
		var h [6]byte
		if _, e := io.ReadFull(c.reader, h[:]); e != nil {
			return 0, e
		}
		c.remaining = int(binary.BigEndian.Uint32(h[:4]))
		c.skip = int(binary.BigEndian.Uint16(h[4:]))
		if c.remaining < 1 || c.remaining > padPayload || c.skip > 63 {
			return 0, errors.New("invalid padding frame")
		}
	}
	if len(out) > c.remaining {
		out = out[:c.remaining]
	}
	n, e := c.reader.Read(out)
	c.remaining -= n
	return n, e
}
func (c *paddedConn) Write(data []byte) (int, error) {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	buf := padPool.Get().([]byte)
	defer padPool.Put(buf)
	written := 0
	for len(data) > 0 {
		n := len(data)
		if n > padPayload {
			n = padPayload
		}
		var one [1]byte
		if _, e := rand.Read(one[:]); e != nil {
			return written, e
		}
		padding := int(one[0] & 63)
		binary.BigEndian.PutUint32(buf[:4], uint32(n))
		binary.BigEndian.PutUint16(buf[4:6], uint16(padding))
		copy(buf[6:6+n], data[:n])
		if _, e := rand.Read(buf[6+n : 6+n+padding]); e != nil {
			return written, e
		}
		frame := buf[:6+n+padding]
		for len(frame) > 0 {
			m, e := c.Conn.Write(frame)
			if e != nil {
				return written, e
			}
			if m == 0 {
				return written, io.ErrShortWrite
			}
			frame = frame[m:]
		}
		written += n
		data = data[n:]
	}
	return written, nil
}
