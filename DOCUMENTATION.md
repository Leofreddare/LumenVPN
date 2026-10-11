# Lumen VPN documentation

## Connect, switch and close

New installations start with an empty VPN list. Imported VPN metadata and preferences are saved in Windows AppData; tokens are saved in Windows Credential Manager when enabled and available. Lumen does not automatically import old connection files.

Import a worker's **client-connection.json** with **Add VPN connections**, then select a location and press Connect. Map pins select a location; Connect starts the VPN. Right-click a location for the same menu as its three-dot button. The three-dot menu supports editing, replacing the connection file and removing a saved location. Favourite stars are filled and move locations to the top by default.

While connecting, the main button can cancel. The small spinner stops after completion; it does not report invented percentage progress. Disconnect waits for routing cleanup and resets uploaded/downloaded totals. X normally hides the window in the Windows notification area. Open it using the tray icon. **Exit** in the tray menu disconnects before quitting. Turn off close-to-tray to disconnect and exit with X instead. If no tray is available, X exits safely.

## Fastest VPN and signal bars

**Fastest VPN** chooses your reachable saved VPN with the lowest recent authenticated response time.

With no location selected, the main button says **Connect to fastest VPN** and uses that choice. Select a location to show **Connect to [name]**; an unchanged default name shows its country instead. A connected VPN shows **Disconnect**. With an empty list, Connect opens the import dialog.

| Bars | Default response time |
| --- | --- |
| Three green | Up to 80 ms |
| Two orange | 81–180 ms |
| One red | Above 180 ms |
| Grey | Not measured or unreachable |

**Latency is waiting time, not download speed.** Hover the bars for measurement age. The active VPN can also show its actual recent traffic rate; no bandwidth capacity is guessed.

Checks authenticate your saved servers, use no third-party speed-test service, and stay in memory. Adjust thresholds, refresh interval and parallel checks in VPN locations. Disable automatic checks there or restrict hostname checks in Privacy and data.

**Map:** click a pin to select, click empty space to deselect, then use Connect. Selecting a map pin leaves an existing connection running. Hover for its country and local flag. Right-click a saved VPN for its edit/favourite/remove menu.

## Preferences

Preferences and Help open in the main window. Choose a category on the left. Back asks you to save, discard or keep editing when there are unsaved changes. Discard restores saved preferences. Save changes applies them and returns to the VPN. Documentation is divided into individual topics, including a separate theme guide.

Changes are stored locally in preferences.json, alongside saved profile metadata in your Windows application configuration folder. Authentication tokens remain in Windows Credential Manager when available. Changes to the network and connection transport take effect on the next connection; a running tunnel is not disrupted. Appearance and display changes preview immediately without writing a file or changing the active connection. Communication settings apply on the next connection after saving. Discard restores the saved appearance. Reset defaults fills the default values; save to apply them.

### App behaviour

- **Close window to tray:** keep the connection running after X; otherwise disconnect and exit.
- **Start in notification area:** hide the window on launch when the tray is available.
- **Connect when app opens:** connect to your selected saved location on launch.
- **Use fastest VPN on startup:** when automatic connection is enabled, measure/select the lowest-latency saved location instead.

These options do not register Windows startup tasks or native Windows VPN providers.

### Appearance

Graphite is the default. Choose Graphite, Midnight, Ocean, Light or an imported custom theme. Set text size, server-list width, row spacing and flag corner radius. Show/hide the map and its hover cards. All graphics are local.

### Animations

Enable/disable animation, set transition duration (100–800 ms), choose 20/30/60 frames per second, and enable/disable the active-map-marker pulse. Reduced motion keeps state changes visible without ongoing animation. Frame rate is a target subject to machine performance.

### Connections

Automatic reconnect is off by default. Configure the retry delay and attempt limit. Explicit disconnect or Exit cancels retries; normal routing may return between attempts.

| Control | What it changes |
| --- | --- |
| Address family | Use IPv4, IPv6 or either for the server connection. |
| TLS connection timeout | Bound DNS resolution and new encrypted connection setup. |
| Relay request timeout | Bound authentication and initial relay responses. |
| TCP keepalive | OS probes for idle links; zero disables them. |
| TLS session resumption | Reuse tickets in memory, with mandatory pinned identity checks. |
| Prepared links | Enable preparation, choose 1–2 links, their lifetime and retry delay. |
| Local SOCKS port | Loopback listener used by the Windows tunnel. |

All options apply on the next connection. Local previews never send a test request. Preparation trades a small amount of resources for faster setup; it does not increase available bandwidth.

### Traffic and DNS

- **MTU:** 1280–1500; default 1400. Match your network path rather than assuming larger is faster.
- **Encrypted DNS:** resolver IP, certificate hostname and TLS port. Queries always go through the relay; the worker rejects private/reserved destinations.
- **Stream buffer:** Auto adapts to hardware; 64/128/256 KiB overrides trade memory for throughput.
- **Concurrent connections:** 8–128 local TCP/UDP associations. Lower values bound memory use; higher values permit more simultaneous traffic.
- **Idle timeout:** 30–900 seconds on client streams; the worker can enforce a shorter limit.
- **UDP queues and batching:** 16–128 queued packets, 1–32 packets per write. Batching drains only ready packets, without waiting. Fixed 256 KiB per-association and 1 MiB global queue budgets remain enforced.
- **Statistics interval:** 1–5 seconds.

Pinning, TLS 1.3, destination restrictions and component integrity checks cannot be disabled. A saved setting changes client behaviour; it cannot override a worker's resource limits or the hosting service's policy.

### VPN locations

Enable automatic latency checks, change interval/timeout and the green/orange thresholds, show/hide numerical latency, choose country/name/latency sorting, and enable/disable favourites-first ordering. There is always a Fastest VPN shortcut. Paused checks can be run on demand by that shortcut while disconnected. Only profiles with available credentials can be measured.

### Privacy and data

- **Display:** show or mask the active VPN address, hide totals, hide recent traffic rates, hide custom server names, and keep the tray location private.
- **Credentials:** choose whether future imported tokens are saved in Windows Credential Manager. Turning this off keeps new tokens in memory for this session; existing vault entries remain.
- **Probes:** disable automatic latency checks in VPN locations, forbid hostname resolution during checks, limit parallel checks, or clear measurements on disconnect. Explicit Fastest VPN checks still contact eligible saved servers.
- **Traffic:** disable UDP or reject tunneled IPv6. These controls block that traffic, so incompatible apps may stop working. TLS identity checking and encryption always remain enabled.
- **Country lookup:** use the local IP database or enter locations manually. Imported hostnames may require OS DNS resolution before a VPN connects.

IP and transfer statistics appear only while connected. No traffic history is written by the client. Your hosting provider can still observe metadata; Lumen cannot enforce its retention policy. There is no persistent kill switch after the tunnel stops.

## Creating themes

Themes are small, **data-only UTF-8 JSON files**. Import them from Preferences → Appearance → Import theme, then save. The file is validated and copied into local preferences; it is not loaded from its original path again. No CSS, Python, JavaScript, images, fonts or URLs can be embedded. Files larger than 16 KiB, invalid colors and unsupported keys are rejected. Export theme writes a reusable JSON file locally.

Example:

```json
{
  "v": 1,
  "name": "Custom slate",
  "colors": {
    "background": "#182129",
    "sidebar": "#202C36",
    "surface": "#293642",
    "border": "#42515F",
    "text": "#EEF2F7",
    "muted": "#A9B6C4",
    "accent": "#9CC8DB",
    "button": "#BED9E4",
    "button_text": "#16242C",
    "map": "#344651",
    "selected": "#395667",
    "good": "#43C89E",
    "medium": "#EFA858",
    "bad": "#ED737D"
  }
}
```

Every color must be exactly **#RRGGBB**. Unspecified color keys inherit Graphite defaults. `background` colors the main window; `sidebar` the location list; `surface` cards/dialog controls; `border` their outlines; `text` primary text; `muted` secondary text; `accent` map markers and emphasis; `button` and `button_text` the connection button; `map` the land; `selected` selected rows; `good`, `medium`, `bad` signal bars. Keep foreground/background contrast readable. Built-in security and connection behavior cannot be changed by a theme.

## Hosting and security limits

The ZIP includes Node.js, Python and Go workers; choose one. On Wispbyte upload all files from server/nodejs, choose Node 24, and set the startup file to start.js. Keep **server-credentials.json** when updating to preserve the server identity. The default exported address is 78.154.103.51:11691; change the PUBLIC_HOST/PUBLIC_PORT environment variables if your host assigns another endpoint. More details are in server/README.md.

This custom tunnel transports supported TCP/UDP system traffic through Wintun and a local engine. UDP travels over TLS/TCP and is affected by TCP loss delays. Local-network traffic, ICMP, broadcasts and multicast are not fully tunneled. There is no persistent firewall kill switch. A VPN does not provide complete anonymity, and the hosting provider may observe metadata or keep its own logs. The Windows native VPN Quick Settings list needs a separate registered VPN-provider package and is not integrated.

## Troubleshooting

- Missing/damaged component: extract the complete client folder again; integrity checks are never bypassed.
- Identity changed: obtain the connection file privately from your trusted hosting panel. Do not accept a replacement from an untrusted source.
- Missing credentials: reimport the connection file, especially if the Windows credential vault was unavailable.
- Gray bars: wait for checks, verify credentials/server availability or use Fastest VPN to measure while disconnected.
- DNS broken after changing settings: restore the default DNS IP/name together and reconnect.
- App hidden: open the tray icon; choose Exit for a complete shutdown.
- Networking settings seem unchanged: disconnect and reconnect to apply them.

## Performance

Lumen uses hardware-sized buffers, bounded queues, independent application-flow connections, TLS session resumption, prepared links and queued UDP batching. These are already enabled where supported.

| Research | Relevant technique | Fit for this worker |
| --- | --- | --- |
| WireGuard | Batch processing and in-place packet transformations | Queue batching is already used. WireGuard's kernel path requires a different protocol. |
| Tailscale | UDP segmentation offload and fewer system calls | Linux UDP offload does not directly apply to this Windows TLS relay. |
| OpenVPN | Kernel data-channel offload; prefer UDP when available | Requires a compatible driver/server. This relay currently transports data over TCP. |
| Proton VPN | Distribute connections across CPU processes; tune congestion control | Node workers already scale within CPU/memory limits. BBR configuration requires host support. |
| Lightway | Dedicated TLS/DTLS protocol and backend | A different client/server protocol; not a drop-in TLS setting. |
| Hysteria | QUIC flow-control and socket-buffer tuning | Requires reachable UDP. Larger windows can use substantially more memory. |
| sing-box | Different TUN network stacks | Test Mixed, System or gVisor in Preferences → Traffic and DNS. Apply by reconnecting. |

**Implemented in this update:** consumed Node UDP parser buffers release their references immediately. This reduces unnecessary buffer retention; it does not establish an Internet-throughput gain.

Address fallback now starts the next candidate immediately after a failed attempt, rather than waiting out the 250 ms stagger. Slow attempts still race with a bounded set of candidates; every candidate must pass the pinned TLS and authenticated capability checks. This adapts Happy Eyeballs connection racing, without claiming full RFC 8305 DNS handling.

Seven alternating local trials with a refused first address and a valid second address measured median authenticated endpoint selection of **254.1 ms before and 2.8 ms after**. This removes avoidable setup delay in that case. It is not a download-speed or Internet-latency benchmark.

**Rejected experiment:** cache-separated per-flow byte counters. Five alternating local trials, 32 MiB of byte-verified echo per flow: one-flow medians 392.8 → 378.2 MiB/s (−3.7%); eight-flow medians 732.0 → 716.7 MiB/s (−2.1%). The change was reverted. These noisy Linux loopback measurements exclude Windows routing, Internet RTT and packet loss.

To tune your connection, compare the same download through the same server, change one setting at a time, and repeat. Test stream-buffer size and MTU; select a nearby low-latency server. The network-stack option is a compatibility/performance experiment, not an automatic speed boost. Privacy checks, encryption and pinning stay enabled.

The largest future architectural option is an authenticated UDP transport where the host exposes UDP. Do not replace reliable TLS with custom unaudited encryption or disable identity checks for a benchmark. A TLS worker cannot exceed its host's bandwidth allocation.

Primary research sources (provided as text; Help does not open links or fetch anything):

- WireGuard: https://www.wireguard.com/papers/wireguard.pdf
- Tailscale: https://tailscale.com/blog/more-throughput
- OpenVPN: https://openvpn.net/as-docs/v3/tutorials/tutorial--vpn-performance-troubleshooting.html
- Proton: https://protonvpn.com/blog/vpn-accelerator
- Lightway: https://github.com/expressvpn/lightway
- Hysteria: https://v2.hysteria.network/docs/advanced/Performance/
- sing-box: https://sing-box.sagernet.org/configuration/inbound/tun/
- Connection racing: https://www.rfc-editor.org/rfc/rfc8305.txt

## Interface references

The update was informed by Proton VPN's documented location list, map, Fastest VPN shortcut and settings organization. Its server-load colors use data from Proton's service; Lumen's bars use your measured response latency and do not claim the same metric.

https://protonvpn.com/support/protonvpn-windows-vpn-application
https://protonvpn.com/support/server-load-percentages-and-colors-explained
https://github.com/ProtonVPN/win-app

This documentation is local. The in-app viewer does not follow links or fetch remote resources.
