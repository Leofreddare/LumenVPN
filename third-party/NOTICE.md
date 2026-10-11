# Bundled components and source

The application's own code is MIT-licensed. The following upstream components retain their own licenses; Lumen's MIT license does not relicense them.

## sing-box 1.14.3

The unmodified official Windows amd64 executable is in `client/bin/sing-box.exe`. Its license is in `client/bin/sing-box-LICENSE.txt`. The exact version's upstream source ZIP, including its build instructions, module manifest, dependency checksums and scripts, is supplied in `client/third-party/source/sing-box-v1.14.3-source.zip`.

Source and build instructions: https://github.com/SagerNet/sing-box/tree/v1.14.3
Direct source archive: https://codeload.github.com/SagerNet/sing-box/zip/refs/tags/v1.14.3
Official release and archive digests: https://github.com/SagerNet/sing-box/releases/tag/v1.14.3

The Go module dependency source locations and versions are specified in the included go.mod/go.sum files and accessible through their upstream repositories and https://proxy.golang.org . The release build workflows and scripts in the source archive describe the official build. No executable modifications have been made.

## Wintun 0.14.1

The official Windows amd64 DLL is in `client/bin/wintun.dll`, with its distribution license in `client/bin/Wintun-LICENSE.txt`.

Official distribution: https://www.wintun.net/builds/wintun-0.14.1.zip
Source: https://git.zx2c4.com/wintun/

## Map and Python packages

`client/assets/world.geojson` is Natural Earth's 110m land geometry, in the public domain.
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson
Terms: https://www.naturalearthdata.com/about/terms-of-use/

PySide6 and keyring are installed by the client user; the Python worker installs cryptography. These packages retain their own upstream licenses.

Installed executable/DLL hashes are pinned in client/engine-manifest.json and checked before connection. No repair downloads are performed by the running app.

## Local icons, flags and geolocation

Lucide SVG icons are bundled in client/assets/icons, under the license in LUCIDE-LICENSE.txt. Source: https://github.com/lucide-icons/lucide . No CDN or remote font is used.

flag-icons 7.3.2 SVG country flags are bundled in client/assets/flags, under FLAG-ICONS-LICENSE.txt (MIT). Source: https://github.com/lipis/flag-icons/tree/v7.3.2 . The neutral globe flag and the small settings/book/lightning SVG additions are original project artwork. The Lumen shield is supplied by the user.

IP Geolocation by DB-IP.com — https://db-ip.com . The bundled IPv4/IPv6 country data is DB-IP Country Lite, distributed under Creative Commons Attribution 4.0 International, with DBIP-LICENSE.txt. Source snapshots: https://github.com/sapics/ip-location-db/tree/main/dbip-country . The supplied CSV ranges were converted into an indexed SQLite database; no additional city data is inferred. This offline snapshot is not automatically updated.

Country display names and approximate map label positions are from Natural Earth's public-domain admin-0 country data: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson . These local files require no requests from the running app.

## Lumen native transport

client/bin/lumen-transport.exe is this project's own MIT-licensed Go transport, compiled for Windows amd64 using Go 1.27.2 with its standard library only. The Go runtime and standard library retain their BSD-style license, supplied as client/bin/Go-LICENSE.txt. Upstream: https://go.dev/ and https://github.com/golang/go . Its source is in client/transport/main.go. No additional Go installation is required to run the client.
