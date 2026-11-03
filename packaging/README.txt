NTSC-RS for OBS

DISCLAIMER
This is a vibe-coded proof of concept. Compatibility, stability and performance
have not been fully tested. Use at your own risk.

A native Windows OBS filter powered by ntsc-rs, bringing live NTSC/VHS effects
to your video sources. Includes ntsc-rs controls, JSON preset import/export,
and adjustable processing resolution and frame rate.

Currently CPU-based and SDR-only. Adds video latency without delaying audio.
Tested with OBS 32.2.2 on Windows.

INSTALLER
Close OBS yourself before installing or uninstalling.
Run the Setup EXE. It installs only this plugin into:
  %ProgramData%\obs-studio\plugins\obs-ntsc-rs
Administrator permission is required. OBS is not installed or modified.
The installer never closes OBS or starts a stream/recording.
Uninstall using Windows Settings > Apps > NTSC-RS for OBS.

MANUAL ZIP
No installer, scripts, or automatic actions are needed.
1. Close OBS.
2. Open %ProgramData%\obs-studio\plugins in File Explorer.
3. Copy the entire obs-ntsc-rs folder from this ZIP into that plugins folder.
   The result must be:
   %ProgramData%\obs-studio\plugins\obs-ntsc-rs\bin\64bit\obs-ntsc-rs.dll
4. Start OBS.
5. Source > Filters > Effect Filters > + > ntsc-rs (NTSC / VHS).

Do not copy only the ZIP itself, and do not put it inside the OBS program folder.
For portable OBS, copy bin\64bit\obs-ntsc-rs.dll into the portable installation's
obs-plugins\64bit folder instead. Do not install a second copy in ProgramData.
To remove a manual installation, close OBS and remove only this plugin's folder
(or its DLL for a portable installation). Other plugins/settings are untouched.

UPDATES
Back up a manually installed plugin before replacing it.
The EXE refuses to overwrite a different manual DLL without an installer marker.
An installer-managed update replaces only the files owned by this installer.
Never install the same plugin into multiple OBS plugin search paths.

REQUIREMENTS / LIMITATIONS
- OBS Studio 32 for Windows. No native Windows ARM build is included.
- Microsoft Visual C++ runtime, normally already present with OBS.
- Default processing limit: 480 lines / 30 effect FPS.
- CPU load and additional video latency depend on source size and settings.
- Audio is not delayed. Set an OBS audio sync offset if needed.
- HDR/unsupported color spaces bypass the effect.
- No long-running capture/streaming stress test has been completed.

TRUST AND SOURCE
Both downloads contain the same plugin DLL.
The EXE and DLL are not code-signed. Windows SmartScreen may show a warning.
The ZIP contains no installer or executable helper, only the plugin DLL,
this guide, license notices, and a data-folder placeholder.
The plugin does not add telemetry, an updater, or network requests.
Source and build scripts must accompany a public release under the GPL.
No public release has been made by the packaging script.

LICENSE
Plugin integration: GPL-2.0-or-later (LICENSE-GPL-2.0.txt).
ntsc-rs core: MIT, selected from its available license options
(LICENSE-ntsc-rs-MIT.txt). Additional dependency notices are in THIRD-PARTY.txt.
