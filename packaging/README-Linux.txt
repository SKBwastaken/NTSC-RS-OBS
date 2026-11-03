NTSC-RS for OBS (Linux)

DISCLAIMER
This is a vibe-coded proof of concept. Compatibility, stability and performance
have not been fully tested. Use at your own risk.

A native OBS filter powered by ntsc-rs, bringing live NTSC/VHS effects to your
video sources. Includes ntsc-rs controls, JSON preset import/export, and
adjustable processing resolution and frame rate.

Currently CPU-based and SDR-only. Adds video latency without delaying audio.

REQUIREMENTS
- OBS Studio 32 or newer, installed as a normal system package
  (for example the official OBS Ubuntu PPA, Arch Linux or Fedora packages).
- 64-bit x86 (x86_64) Linux with glibc 2.39 or newer
  (for example Ubuntu 24.04 or newer, Debian 13, Fedora 40 or newer).
- This ZIP is not for Flatpak or Snap OBS. For the experimental, separately built
  Flatpak extension, see docs/FLATPAK.md in the source repository.

INSTALL
1. Close OBS.
2. Open the folder ~/.config/obs-studio/plugins
   (create the "plugins" folder if it does not exist yet).
   The folder starting with a dot is hidden; press Ctrl+H in most file managers.
3. Copy the entire obs-ntsc-rs folder from this ZIP into that plugins folder.
   The result must be:
   ~/.config/obs-studio/plugins/obs-ntsc-rs/bin/64bit/obs-ntsc-rs.so
4. Start OBS.
5. Source > Filters > Effect Filters > + > ntsc-rs (NTSC / VHS).

REMOVE
Close OBS and delete only ~/.config/obs-studio/plugins/obs-ntsc-rs.
Other plugins and settings are untouched.

LIMITATIONS
- Default processing limit: 480 lines / 30 effect FPS.
- CPU load and additional video latency depend on source size and settings.
- Audio is not delayed. Set an OBS audio sync offset if needed.
- HDR/unsupported color spaces bypass the effect.
- Tested automatically in an isolated OBS environment on Ubuntu 24.04 with
  software OpenGL. Not tested with a real desktop session, camera, game
  capture or long-running streams.

TRUST AND SOURCE
The ZIP contains only the plugin library, this guide, license notices, and a
data-folder placeholder. The plugin does not add telemetry, an updater, or
network requests. Source and build scripts are published with the release.

LICENSE
Plugin integration: GPL-2.0-or-later (LICENSE-GPL-2.0.txt).
ntsc-rs core: MIT, selected from its available license options
(LICENSE-ntsc-rs-MIT.txt). Additional dependency notices are in THIRD-PARTY.txt.
