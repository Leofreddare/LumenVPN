// Lumen native loopback SOCKS5 transport. MIT; no activity logging.
package main

import (
	"bufio"
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"crypto/tls"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"runtime"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

type config struct {
	Host           string `json:"host"`
	Port           int    `json:"port"`
	Token          string `json:"token"`
	Pin            string `json:"fingerprint"`
	Local          int    `json:"local_port"`
	Warm           bool   `json:"warm"`
	Chunk          int    `json:"chunk"`
	DialTimeout    int    `json:"dial_timeout"`
	RequestTimeout int    `json:"request_timeout"`
	KeepAlive      int    `json:"tcp_keepalive"`
	WarmCount      int    `json:"warm_count"`
	WarmLifetime   int    `json:"warm_lifetime"`
	WarmRetry      int    `json:"warm_retry"`
	MaxConnections int    `json:"max_connections"`
	IdleTimeout    int    `json:"idle_timeout"`
	UDPQueue       int    `json:"udp_queue_packets"`
	UDPBatch       int    `json:"udp_batch_packets"`
	Resume         bool   `json:"session_resumption"`
	AllowUDP       bool   `json:"allow_udp"`
}
type prepared struct {
	conn   net.Conn
	reader *bufio.Reader
	at     time.Time
}
type proxy struct {
	cfg      config
	ctx      context.Context
	cancel   context.CancelFunc
	tls      *tls.Config
	mu       sync.Mutex
	conns    map[net.Conn]bool
	warm     []prepared
	pending  int
	retry    time.Time
	slots    chan struct{}
	wg       sync.WaitGroup
	up, down atomic.Uint64
	queued   atomic.Int64
}

func (p *proxy) track(c net.Conn) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.ctx.Err() != nil {
		c.Close()
		return false
	}
	p.conns[c] = true
	return true
}
func (p *proxy) close(c net.Conn) {
	c.SetDeadline(time.Now())
	c.Close()
	p.mu.Lock()
	delete(p.conns, c)
	p.mu.Unlock()
}
func (p *proxy) open() (net.Conn, error) {
	ctx, cancel := context.WithTimeout(p.ctx, time.Duration(p.cfg.DialTimeout)*time.Second)
	defer cancel()
	keepalive := time.Duration(p.cfg.KeepAlive) * time.Second
	if p.cfg.KeepAlive == 0 {
		keepalive = -1
	}
	d := tls.Dialer{NetDialer: &net.Dialer{Timeout: time.Duration(p.cfg.DialTimeout) * time.Second, KeepAlive: keepalive}, Config: p.tls}
	c, e := d.DialContext(ctx, "tcp", net.JoinHostPort(p.cfg.Host, strconv.Itoa(p.cfg.Port)))
	if e != nil {
		return nil, e
	}
	if !p.track(c) {
		return nil, context.Canceled
	}
	return c, nil
}
func (p *proxy) request(c net.Conn, r *bufio.Reader, action, host string, port int) error {
	c.SetDeadline(time.Now().Add(time.Duration(p.cfg.RequestTimeout) * time.Second))
	req := map[string]any{"v": 1, "token": p.cfg.Token, "action": action}
	if host != "" {
		req["host"] = host
		req["port"] = port
	}
	b, _ := json.Marshal(req)
	if _, e := c.Write(append(b, '\n')); e != nil {
		return e
	}
	// No large untrusted response allocation, even if the peer is malformed.
	line := make([]byte, 0, 256)
	for len(line) <= 1024 {
		b, e := r.ReadByte()
		if e != nil {
			return e
		}
		if b == '\n' {
			var reply struct {
				OK bool `json:"ok"`
			}
			if json.Unmarshal(line, &reply) != nil || !reply.OK {
				return errors.New("relay rejected")
			}
			c.SetDeadline(time.Time{})
			return nil
		}
		line = append(line, b)
	}
	return errors.New("invalid response")
}
func (p *proxy) fill() {
	if !p.cfg.Warm {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.ctx.Err() != nil || time.Now().Before(p.retry) {
		return
	}
	for len(p.warm)+p.pending < p.cfg.WarmCount {
		p.pending++
		p.wg.Add(1)
		go func() {
			defer p.wg.Done()
			c, e := p.open()
			var r *bufio.Reader
			if e == nil {
				r = bufio.NewReaderSize(c, 4096)
				e = p.request(c, r, "warm", "", 0)
			}
			p.mu.Lock()
			p.pending--
			if e == nil && p.ctx.Err() == nil {
				p.warm = append(p.warm, prepared{c, r, time.Now()})
				c = nil
			} else if e != nil {
				p.retry = time.Now().Add(time.Duration(p.cfg.WarmRetry) * time.Second)
			}
			p.mu.Unlock()
			if c != nil {
				p.close(c)
			}
		}()
	}
}
func (p *proxy) remote(action, host string, port int) (net.Conn, *bufio.Reader, error) {
	p.mu.Lock()
	var item *prepared
	if n := len(p.warm); n > 0 {
		v := p.warm[n-1]
		p.warm = p.warm[:n-1]
		item = &v
	}
	p.mu.Unlock()
	p.fill()
	if item != nil {
		if time.Since(item.at) < time.Duration(p.cfg.WarmLifetime)*time.Second {
			if e := p.request(item.conn, item.reader, action, host, port); e == nil {
				return item.conn, item.reader, nil
			}
		}
		p.close(item.conn)
	}
	c, e := p.open()
	if e != nil {
		return nil, nil, e
	}
	r := bufio.NewReaderSize(c, 4096)
	if e = p.request(c, r, action, host, port); e != nil {
		p.close(c)
		return nil, nil, e
	}
	return c, r, nil
}
func readAddress(r io.Reader, kind byte) (string, int, error) {
	var b []byte
	switch kind {
	case 1:
		b = make([]byte, 4)
	case 4:
		b = make([]byte, 16)
	case 3:
		var n [1]byte
		if _, e := io.ReadFull(r, n[:]); e != nil {
			return "", 0, e
		}
		if n[0] == 0 {
			return "", 0, errors.New("empty host")
		}
		b = make([]byte, int(n[0]))
	default:
		return "", 0, errors.New("address")
	}
	if _, e := io.ReadFull(r, b); e != nil {
		return "", 0, e
	}
	var port [2]byte
	if _, e := io.ReadFull(r, port[:]); e != nil {
		return "", 0, e
	}
	host := string(b)
	if kind != 3 {
		host = net.IP(b).String()
	}
	return host, int(binary.BigEndian.Uint16(port[:])), nil
}

var buffers = sync.Pool{New: func() any { return make([]byte, 65536) }}
var streamSize = 65536
var streamBuffers = sync.Pool{New: func() any { return make([]byte, streamSize) }}

type activity struct {
	left, right net.Conn
	updated     atomic.Int64
	idle        time.Duration
}

func (a *activity) touch() {
	now := time.Now()
	prev := a.updated.Load()
	if now.UnixNano()-prev >= int64(time.Second) && a.updated.CompareAndSwap(prev, now.UnixNano()) {
		a.left.SetReadDeadline(now.Add(a.idle))
		a.right.SetReadDeadline(now.Add(a.idle))
	}
}
func copyData(dst net.Conn, src io.Reader, stats *atomic.Uint64, a *activity) {
	b := streamBuffers.Get().([]byte)
	defer streamBuffers.Put(b)
	var last int64
	for {
		a.touch()
		n, e := src.Read(b)
		if n > 0 {
			now := time.Now()
			if now.UnixNano()-last >= int64(time.Second) {
				dst.SetWriteDeadline(now.Add(a.idle))
				last = now.UnixNano()
			}
			written, err := dst.Write(b[:n])
			stats.Add(uint64(written))
			a.touch()
			if err != nil {
				return
			}
		}
		if e != nil {
			return
		}
	}
}

func (p *proxy) tcp(local net.Conn, host string, port int) error {
	remote, r, e := p.remote("connect", host, port)
	if e != nil {
		return e
	}
	defer p.close(remote)
	local.SetDeadline(time.Time{})
	if _, e = local.Write([]byte{5, 0, 0, 1, 0, 0, 0, 0, 0, 0}); e != nil {
		return e
	}
	a := &activity{left: local, right: remote, idle: time.Duration(p.cfg.IdleTimeout) * time.Second}
	a.touch()
	done := make(chan int, 2)
	go func() { copyData(remote, local, &p.up, a); done <- 0 }()
	go func() { copyData(local, r, &p.down, a); done <- 1 }()
	direction := <-done
	if direction == 0 {
		<-done
	} else {
		local.Close()
		remote.Close()
		<-done
	}
	return nil
}
func (p *proxy) udp(local net.Conn, expected int) error {
	remote, r, e := p.remote("udp", "", 0)
	if e != nil {
		return e
	}
	defer p.close(remote)
	sock, e := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if e != nil {
		return e
	}
	defer sock.Close()
	port := sock.LocalAddr().(*net.UDPAddr).Port
	reply := []byte{5, 0, 0, 1, 127, 0, 0, 1, byte(port >> 8), byte(port)}
	local.SetDeadline(time.Time{})
	if _, e = local.Write(reply); e != nil {
		return e
	}
	ctx, cancel := context.WithCancel(p.ctx)
	defer cancel()
	done := make(chan struct{}, 3)
	queue := make(chan []byte, p.cfg.UDPQueue)
	var peerMu sync.Mutex
	var peer *net.UDPAddr
	var queued atomic.Int64
	var jobs sync.WaitGroup
	jobs.Add(4)
	go func() { defer jobs.Done(); defer func() { done <- struct{}{} }(); var one [1]byte; local.Read(one[:]) }()
	go func() {
		defer jobs.Done()
		defer func() { done <- struct{}{} }()
		var prefix [4]byte
		buffer := buffers.Get().([]byte)
		defer buffers.Put(buffer)
		for {
			if _, e := io.ReadFull(r, prefix[:]); e != nil {
				return
			}
			n := binary.BigEndian.Uint32(prefix[:])
			if n < 7 || n > 65535 {
				return
			}
			b := buffer[:n]
			if _, e := io.ReadFull(r, b); e != nil {
				return
			}
			peerMu.Lock()
			addr := peer
			peerMu.Unlock()
			if addr != nil {
				if _, e := sock.WriteToUDP(b, addr); e == nil {
					p.down.Add(uint64(len(b)))
				}
			}
		}
	}()
	go func() {
		defer jobs.Done()
		b := make([]byte, 65535)
		for {
			n, addr, e := sock.ReadFromUDP(b)
			if e != nil {
				return
			}
			if !addr.IP.Equal(net.IPv4(127, 0, 0, 1)) || n < 7 || b[0] != 0 || b[1] != 0 || b[2] != 0 || expected != 0 && addr.Port != expected {
				continue
			}
			peerMu.Lock()
			if peer == nil {
				peer = addr
			}
			match := addr.Port == peer.Port && addr.IP.Equal(peer.IP)
			peerMu.Unlock()
			if !match {
				continue
			}
			if queued.Add(int64(n)) > 262144 {
				queued.Add(-int64(n))
				continue
			}
			if p.queued.Add(int64(n)) > 1048576 {
				queued.Add(-int64(n))
				p.queued.Add(-int64(n))
				continue
			}
			packet := append([]byte(nil), b[:n]...)
			select {
			case queue <- packet:
			default:
				queued.Add(-int64(n))
				p.queued.Add(-int64(n))
			}
		}
	}()
	go func() {
		defer jobs.Done()
		defer func() { done <- struct{}{} }()
		batch := make([]byte, 0, 131072)
		for {
			select {
			case <-ctx.Done():
				return
			case packet := <-queue:
				frames := batch[:0]
				total := 0
				for count := 0; ; count++ {
					var prefix [4]byte
					binary.BigEndian.PutUint32(prefix[:], uint32(len(packet)))
					frames = append(frames, prefix[:]...)
					frames = append(frames, packet...)
					total += len(packet)
					queued.Add(-int64(len(packet)))
					p.queued.Add(-int64(len(packet)))
					if count >= p.cfg.UDPBatch-1 || total >= 65536 {
						break
					}
					select {
					case packet = <-queue:
					default:
						packet = nil
					}
					if packet == nil {
						break
					}
				}
				remote.SetWriteDeadline(time.Now().Add(time.Duration(p.cfg.RequestTimeout) * time.Second))
				if _, e := remote.Write(frames); e != nil {
					return
				}
				p.up.Add(uint64(total))
			}
		}
	}()
	<-done
	cancel()
	sock.Close()
	local.Close()
	remote.Close()
	jobs.Wait()
	for {
		select {
		case packet := <-queue:
			queued.Add(-int64(len(packet)))
			p.queued.Add(-int64(len(packet)))
		default:
			return nil
		}
	}
}
func (p *proxy) handle(c net.Conn) {
	defer p.wg.Done()
	defer func() { <-p.slots }()
	defer p.close(c)
	c.SetDeadline(time.Now().Add(time.Duration(p.cfg.RequestTimeout) * time.Second))
	var hello [2]byte
	if _, e := io.ReadFull(c, hello[:]); e != nil || hello[0] != 5 || hello[1] == 0 {
		return
	}
	methods := make([]byte, int(hello[1]))
	if _, e := io.ReadFull(c, methods); e != nil {
		return
	}
	valid := false
	for _, m := range methods {
		if m == 0 {
			valid = true
		}
	}
	if !valid {
		c.Write([]byte{5, 255})
		return
	}
	if _, e := c.Write([]byte{5, 0}); e != nil {
		return
	}
	var req [4]byte
	if _, e := io.ReadFull(c, req[:]); e != nil || req[0] != 5 || req[2] != 0 {
		return
	}
	host, port, e := readAddress(c, req[3])
	if e != nil {
		return
	}
	switch req[1] {
	case 1:
		e = p.tcp(c, host, port)
	case 3:
		if !p.cfg.AllowUDP {
			e = errors.New("UDP disabled")
		} else {
			e = p.udp(c, port)
		}
	default:
		e = errors.New("command")
	}
	if e != nil {
		c.Write([]byte{5, 1, 0, 1, 0, 0, 0, 0, 0, 0})
	}
}
func run() error {
	input := bufio.NewReaderSize(os.Stdin, 4096)
	line, e := input.ReadSlice('\n')
	if e != nil {
		return e
	}
	cfg := config{DialTimeout: 15, RequestTimeout: 15, KeepAlive: 30, WarmCount: 2, WarmLifetime: 20, WarmRetry: 5, MaxConnections: 128, IdleTimeout: 300, UDPQueue: 128, UDPBatch: 32, Resume: true, AllowUDP: true}
	if json.Unmarshal(line, &cfg) != nil {
		return errors.New("config")
	}
	if cfg.DialTimeout < 3 || cfg.DialTimeout > 30 || cfg.RequestTimeout < 2 || cfg.RequestTimeout > 30 || cfg.KeepAlive < 0 || cfg.KeepAlive > 120 || cfg.WarmCount < 1 || cfg.WarmCount > 2 || cfg.WarmLifetime < 5 || cfg.WarmLifetime > 20 || cfg.WarmRetry < 1 || cfg.WarmRetry > 30 || cfg.MaxConnections < 8 || cfg.MaxConnections > 128 || cfg.IdleTimeout < 30 || cfg.IdleTimeout > 900 || cfg.UDPQueue < 16 || cfg.UDPQueue > 128 || cfg.UDPBatch < 1 || cfg.UDPBatch > 32 {
		return errors.New("config range")
	}
	if cfg.Chunk == 131072 || cfg.Chunk == 262144 {
		streamSize = cfg.Chunk
	}
	pin, e := hex.DecodeString(cfg.Pin)
	if e != nil || len(pin) != 32 || net.ParseIP(cfg.Host) == nil || cfg.Port < 1 || cfg.Port > 65535 || cfg.Local < 1024 || cfg.Local > 65535 || len(cfg.Token) < 32 || len(cfg.Token) > 512 {
		return errors.New("config")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	p := &proxy{cfg: cfg, ctx: ctx, cancel: cancel, conns: map[net.Conn]bool{}, slots: make(chan struct{}, cfg.MaxConnections)}
	p.tls = &tls.Config{MinVersion: tls.VersionTLS13, InsecureSkipVerify: true, ClientSessionCache: tls.NewLRUClientSessionCache(32), VerifyConnection: func(state tls.ConnectionState) error {
		if len(state.PeerCertificates) == 0 {
			return errors.New("identity")
		}
		got := sha256.Sum256(state.PeerCertificates[0].Raw)
		if subtle.ConstantTimeCompare(got[:], pin) != 1 {
			return errors.New("identity")
		}
		return nil
	}}
	if !cfg.Resume {
		p.tls.ClientSessionCache = nil
	}
	listener, e := net.Listen("tcp4", net.JoinHostPort("127.0.0.1", strconv.Itoa(cfg.Local)))
	if e != nil {
		return e
	}
	defer listener.Close()
	go func() { input.ReadString('\n'); cancel(); listener.Close() }()
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				p.mu.Lock()
				ready := p.warm[:0]
				var expired []net.Conn
				for _, w := range p.warm {
					if time.Since(w.at) >= time.Duration(p.cfg.WarmLifetime)*time.Second {
						expired = append(expired, w.conn)
					} else {
						ready = append(ready, w)
					}
				}
				p.warm = ready
				p.mu.Unlock()
				for _, c := range expired {
					p.close(c)
				}
				b, _ := json.Marshal(map[string]any{"up": p.up.Load(), "down": p.down.Load()})
				fmt.Println(string(b))
			}
		}
	}()
	p.fill()
	fmt.Printf("{\"ready\":true,\"cpus\":%d}\n", runtime.GOMAXPROCS(0))
	for {
		c, e := listener.Accept()
		if e != nil {
			break
		}
		select {
		case p.slots <- struct{}{}:
			if p.track(c) {
				p.wg.Add(1)
				go p.handle(c)
			} else {
				<-p.slots
			}
		default:
			c.Close()
		}
	}
	cancel()
	p.mu.Lock()
	for c := range p.conns {
		c.SetDeadline(time.Now())
		c.Close()
	}
	p.mu.Unlock()
	p.wg.Wait()
	return nil
}
func main() {
	if run() != nil {
		fmt.Println("{\"error\":true}")
		os.Exit(1)
	}
}
