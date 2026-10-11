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

Five alternating local Linux trials compared the previous Python forwarding client and single Node worker against the new native client and two Node workers. Each TCP flow echoed 32 MiB with byte verification; the echo target ran in a separate process. Medians:

| Workload | Previous | Updated | Change |
| --- | ---: | ---: | ---: |
| One flow | 364.5 MiB/s | 346.6 MiB/s | −4.9% |
| Eight concurrent flows | 323.6 MiB/s | 772.8 MiB/s | +138.8% |

This CPU-limited loopback benchmark exceeds a 15% improvement for concurrent flows, but **does not establish a universal 15% gain**. It excludes the Windows driver and Internet bandwidth, congestion and packet loss. The one-flow result was lower. Compression is not enabled: much Internet traffic is already compressed/encrypted, and compression of secrets alongside attacker-controlled data can expose information.

## Privacy and limits

DNS uses an encrypted resolver through the relay. The engine has no direct outbound fallback; traffic logging is disabled. New imported tokens optionally use Windows Credential Manager; if unavailable, reimport after restarting. The connection file is secret. Certificate pinning stays enabled.

There is **no persistent firewall kill switch**: disconnecting, switching servers or a crash can restore normal routing. Local-network traffic, ICMP, broadcast and multicast are not fully tunneled. UDP travels over TLS/TCP and inherits TCP loss delays. Your hosting provider can observe source IPs and traffic metadata and may keep its own logs. This is not an anonymity guarantee.

Automated checks cover all three workers, native forwarding, pin/token rejection, TCP/UDP, queue/resource limits, prepared connections, credential preservation, tray/exit states and counter reset. Go integration uses the race detector. Live Windows driver, tray, routing and leak behaviour could not be tested in this Linux workspace.

The Performance topic in Help reviews seven VPN implementations and protocol families, explains which techniques fit this worker, and records the rejected counter experiment. A Windows TUN stack selector supports Mixed (default), System and gVisor. Node consumes and releases UDP parser chunks sooner to reduce retained buffers. No new Internet-speed improvement is claimed.

## Fastest connection button and fallback

With no location selected, Connect to fastest VPN chooses the lowest recent authenticated response latency. A selected location shows its custom name, or its country when the name is unchanged. Connected sessions show Disconnect. You can cancel location measurement with the main button.

Failed endpoint attempts now advance immediately to the next address; slow attempts remain staggered. Seven alternating pinned-TLS local trials with the first address refused measured median endpoint selection of 254.1 ms before and 2.8 ms after. This demonstrates reduced fallback setup delay, not higher download throughput or lower Internet RTT.
