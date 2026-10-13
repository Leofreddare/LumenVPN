# Lumen VPN — Windows x64

Install this folder's packages using your existing Python:

`python -m pip install -r requirements.txt`

A fresh install has no VPNs. Manually imported locations and preferences are saved in the Windows AppData application folder; tokens use Windows Credential Manager when enabled and available. Old connection files are not imported automatically. Keep the complete folder together. Double-click **app.pyw**, accept the administrator prompt and import **client-connection.json** with Add VPN connections. Map pins select a location; the Connect button starts it. Clicking empty map space deselects. Favourites move to the top. The three-dot menu supports editing, reimporting and removing connections. No batch launcher, virtual environment or automatic dependency installer is used.

The in-app top-left branding and SERVER ENDPOINT heading have been removed. The active endpoint and upload/download totals are hidden until connected. The Windows window title remains **Lumen VPN**. Uploaded/downloaded counters reset after disconnect; delayed statistics cannot restore old totals.

## Interface, settings and themes

The connection button uses a small time-based spinner and a smooth connected-state color transition. The overlapping Cancel label is removed; clicking the Connecting button still cancels. The map pulse is restrained; hidden views stop their timers. Favourites use filled stars; flags have rounded corners. Hover map pins for the country, flag and city/name.

**Fastest VPN** selects the saved location with the lowest recent authenticated relay response latency. Green/orange/red bars use configurable latency thresholds; gray means untested or unreachable. Only saved servers are contacted, with a configurable 1–4 probes at a time, while disconnected. The bars are not measured bandwidth or server load. Hover the active location's bars for actual recent traffic in Mbps, which is current usage rather than maximum capacity.

The top-right cog opens Preferences **inside the main window**, with switches, compact number controls, a theme selector and compact option explanations. **65 options in seven categories**: Appearance, Animations, App behaviour, Connections, Traffic and DNS, VPN locations and Privacy and data. Graphite is the default. Four local themes are included; import/export custom data-only JSON themes. Communication changes apply on the next connection: address family, TLS timeouts/session resumption, TCP keepalives, prepared-link limits, connection limits, UDP queues/batching, idle timeout, and encrypted DNS port. Privacy controls can mask the endpoint, hide counters/names, suppress hostname probes, forget latency on disconnect and block tunneled IPv6 or UDP. TLS pinning and encrypted DNS remain mandatory. The book icon opens Help inside the main window, divided into **15 browsable topics**, including theme format, individual settings categories and troubleshooting. Back returns to the VPN. Appearance previews immediately without saving; Back prompts for unsaved changes, and Discard restores saved values; Save changes applies them. Documentation uses static topics and tables, with no interactive exercises. All icons, system fonts, flags, maps and help content are local; the help viewer blocks resource loading and external link navigation. DOCUMENTATION.md is also supplied as a local reference.

## Closing and background operation

On Windows, closing the window with X hides it in the notification area and keeps the connection running. The tray menu has Open, Connect/Disconnect and **Exit**. Exit disconnects and waits for tunnel cleanup before closing. If the tray is unavailable, closing the window disconnects and exits instead. Closing during startup also waits for cleanup.

Windows' native VPN Quick Settings list is not integrated. This custom protocol would require a registered Windows VPN provider package and a separate background-provider implementation. A tray shortcut is available; a nonfunctional Windows VPN profile is not created.

## Networking and hardware

The x64 native forwarding executable, system-tunnel engine and Wintun driver are included and their SHA-256 hashes are verified before use. No Go installation is needed. Python handles the interface; compiled Go handles forwarding with multiple CPU cores, pooled buffers and bounded queues. Credentials go to the child over a private stdin pipe, not command-line arguments. The parent closes that pipe during shutdown; the child then closes its connections.

Hardware detection is local. Available memory and CPU limits select TCP buffers of 64, 128 or 256 KiB, rather than allocating all RAM. The TLS implementation can use platform cryptographic acceleration. Session tickets stay in process memory; the certificate pin is verified even on resumed sessions. No TLS 0-RTT is used.

Each application flow has an independent TLS 1.3 connection. A configurable one or two authenticated connections can be prepared when the worker supports it. They expire after the configured 5–20 seconds without idle refills or keepalives. This reduces setup latency but still requires handshake work. Already-queued UDP packets are batched without an added delay; queues share a 1 MiB budget, with per-association limits. Congestion can cause UDP drops. Endpoint selection probes pinned IPv4/IPv6 connections before installing routes and uses the selected address thereafter.

The shield, flags, map, icons and country database are local. The running interface fetches no remote assets. Country labels use approximate offline geolocation. Map geometry is cached and hidden maps stop animating. Attribution and required engine source are in third-party/.

## Measured performance

The map path is precomputed from the original geometry; all 4,478 path elements compare equal. Networking imports, offline database imports and the geolocation thread are deferred until needed. The interface layout, colours, animations and icons are unchanged.

Seven alternating Linux/offscreen first-window trials with empty profiles measured medians of 0.228 s before and 0.179 s after (21.8% faster). Peak process memory fell from 72788 KiB to 64220 KiB (11.8%). These are small local trials, not a guarantee for every machine. In 25 map-construction trials per version, the map's median construction time fell from 4.53 ms to 1.49 ms. Measurements exclude a Windows packaged EXE, driver startup and connecting to the Internet. A single-file EXE still extracts bundled components at launch; instantaneous launch on every PC is not promised.

Buffers, queues and worker counts stay bounded rather than consuming all RAM/CPU or sending idle filler traffic. Session reuse, independent flows, pooled Go buffers, CPU-aware Node workers and Rust's asynchronous scheduler remain available. Padding adds bytes and can reduce throughput. Compression of mixed secret and attacker-controlled data is deliberately disabled. No new Internet throughput gain is claimed.

## Privacy and limits

The bundled Unbound 1.26.1 process (built with OpenSSL 3.5.9) validates DNSSEC locally using IANA root trust anchors, caches answers only in memory, and forwards DNS over verified TLS 1.3 through the VPN. The only direct engine outbound is an internal loopback path to the validator; the default application route remains the relay. Traffic/query logging is disabled. New imported tokens optionally use Windows Credential Manager; if unavailable, reimport after restarting. The connection file is secret. Certificate pinning stays enabled.

There is **no persistent firewall kill switch**: disconnecting, switching servers or a crash can restore normal routing. Local-network traffic, ICMP, broadcast and multicast are not fully tunneled. UDP travels over TLS/TCP and inherits TCP loss delays. Your hosting provider can observe source IPs and traffic metadata and may keep its own logs. This is not an anonymity guarantee.

This update was tested against all four workers using TLS authentication, public-IP rejection, TCP/UDP, fragmented padded frames, prepared connections, malformed frames and the compiled Go client. Domain SOCKS requests resolve through a configured loopback DNS port and arrive at the workers as IPs. A local signed-zone TLS fixture verified DNSSEC signature rejection, caching and certificate-hostname rejection; public signed/bogus/unsigned records were also checked through a test TLS-to-DoH bridge. The engine configuration passed sing-box's checker; the Windows forwarding EXE and updated DNS executable were cross-compiled. The DNS build requires TLS 1.3 and rejected TLS 1.2-only upstreams in the source test. Live Windows driver, routing, tray and leak behaviour were not exercised here.

The Performance topic in Help reviews seven VPN implementations and protocol families, explains which techniques fit this worker, and records the rejected counter experiment. A Windows TUN stack selector supports Mixed (default), System and gVisor. Node consumes and releases UDP parser chunks sooner to reduce retained buffers. No new Internet-speed improvement is claimed.

## Fastest connection button and fallback

With no location selected, Connect to fastest VPN chooses the lowest recent authenticated response latency. A selected location shows its custom name, or its country when the name is unchanged. Connected sessions show Disconnect. You can cancel location measurement with the main button.

Failed endpoint attempts now advance immediately to the next address; slow attempts remain staggered. Seven alternating pinned-TLS local trials with the first address refused measured median endpoint selection of 254.1 ms before and 2.8 ms after. This demonstrates reduced fallback setup delay, not higher download throughput or lower Internet RTT.

## Security update and compatibility

The client-server transport keeps pinned TLS 1.3 and standard authenticated encryption. More encryption layers or custom ciphers are not added. Server-side destination hostname lookup is disabled by default in every implementation: the updated native client resolves names locally. Older clients that send hostnames need `ALLOW_REMOTE_DNS=1` during migration; that opt-in lets the worker see/resolve the hostname. Preserve `server-credentials.json` and existing trusted pairing files when upgrading.

New workers advertise `padding-v1`. The client automatically negotiates it and places 0–63 cryptographically random padding bytes around each 1–32,768-byte TCP data frame inside TLS. No deliberate delay or idle cover traffic is added. UDP framing is unchanged. These are stream frames, not guaranteed IP-packet sizes; timings, traffic bursts, volumes and destination IPs remain observable.

DNSSEC protects signed zones; unsigned domains lack authenticated DNS records. The resolver still needs upstream DNS data—an Internet-wide DNS database cannot be entirely offline. Bundled public CA roots verify the DNS-over-TLS hostname; no machine-specific trust store is bundled. VPN endpoint hostnames and saved-hostname probes can still use the OS resolver before connection. Use numeric VPN endpoints and disable hostname probes to avoid that bootstrap lookup. Update bundled DNS roots/CA data through a trusted release when necessary; no background asset fetcher runs.

A provider with process/memory access can inspect the VPN's decrypted exit traffic, destination IPs and client metadata, even without filesystem access. Website HTTPS and DNS-over-TLS are separate end-to-end layers, but visible SNI and traffic correlation can still reveal activity. A single relay cannot make a hostile exit blind or guarantee anonymity. No persistent firewall kill switch is included.
