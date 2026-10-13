# Build a single Lumen VPN.exe

Place build.bat, build_client.py and frozen_entry.py in your complete client folder beside app.pyw. Double-click build.bat using your existing 64-bit Python on Windows x64. Internet access is needed to download build dependencies.

The build leaves exactly one new output: **Lumen VPN.exe**, in that same client folder. No dist folder, release ZIP, hashes file or loose license files are created there. Your existing client files and build-kit files remain in place. You can distribute the EXE by itself; the target computer needs no Python installation.

Temporary dependencies, staged source, specs and intermediate build output live in an operating-system temporary directory and are removed on success or a handled failure. No virtual environment or global dependency installation is used. An abrupt power loss or forced process termination can leave an OS temporary directory. Existing dist folders from older builds are not deleted.

The client/build/home paths and computer name are checked, including compressed Python code and bundled data. Saved VPNs, tokens, connection files, preferences, logs, caches and SQLite journals are excluded. Networking component hashes are verified before packaging. No UPX or obfuscation is used; antivirus false positives are still possible. Nothing is uploaded to VirusTotal.

Required third-party notices, dependency licenses and any supplied third-party source archives are **inside the executable**, not separate output files. To access them deliberately, run:

```bat
"Lumen VPN.exe" --export-notices "Lumen-notices"
```

This optional command creates the named folder only when requested. Keep the supplied third-party source/notice files in the client before building; the kit cannot manufacture missing corresponding source. Do not remove notices when distributing the executable.

The EXE is published only after validation. A failed build leaves any previous Lumen VPN.exe intact, and removes its temporary publication file. If the old EXE is running, close it before rebuilding.

The frozen entry point handles cleanup helper subprocesses without needing Python on the target. Windows asks for administrator permission for the VPN adapter. Normal per-user settings remain in Windows AppData/Credential Manager at runtime; those settings are not part of the EXE.

Staging, syntax, output publication and cleanup were checked in the preparation environment. The final Windows executable and live tunnel still require a Windows build and test.

The supplied shield-with-L image is embedded in the kit as a seven-resolution Windows icon. Every build uses it for the EXE and the app window, replacing any older client icon in temporary staging. The original client assets are not modified. No loose icon file is created in the client folder.

The build now includes the local Unbound executable, public DNS CA bundle/root anchors and precomputed map path. Their integrity is checked. Local DNS's watchdog is also dispatched through the EXE helper entry point, so it does not require Python on the target. Stored profiles, tokens, custom CA certificates, build caches and server keys are excluded. A single-file EXE extracts bundled components at launch; this has startup cost on slow disks. Windows building and live full-system leak testing remain necessary.
