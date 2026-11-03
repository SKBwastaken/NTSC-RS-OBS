NTSC-RS for OBS, Flatpak extension (x86_64)

STATUS AND DISCLAIMER
Experimental. This bundle was built from source and tested automatically in
GitHub Actions inside the real OBS Flatpak sandbox (Ubuntu 24.04, virtual
display, software OpenGL): plugin loading, video processing, presets and
sandboxed file access. It has NOT yet been tested in the OBS desktop interface
on a real Linux desktop (file chooser/portal, Wayland, real GPUs, capture
devices, long runs). This is a vibe-coded proof of concept. Use at your own risk.

REQUIREMENTS
- OBS Studio from Flathub, app ID com.obsproject.Studio, branch stable, x86_64.
  The release notes list the OBS and runtime versions used for the test.
- Do not use the Linux system-package ZIP with Flatpak, or this bundle with
  system-package OBS. Snap is not supported.

INSTALL
1. Close Flatpak OBS yourself. The installer never stops OBS.
2. Install the downloaded bundle in the same scope as OBS.
   Check the scope with: flatpak list --app --columns=application,installation
   Per-user OBS:
     flatpak install --user ./NTSC-RS-OBS-<version>-Flatpak-x86_64.flatpak
   System-wide OBS (asks for administrator authorization):
     flatpak install --system ./NTSC-RS-OBS-<version>-Flatpak-x86_64.flatpak
3. Start OBS as usual: flatpak run com.obsproject.Studio
4. Source > Filters > Effect Filters > + > ntsc-rs (NTSC / VHS).

This is a local, unsigned bundle, not a Flathub listing or an automatic updater.
Verify its origin. Do not add a permanent remote or disable signature checks
globally. Use the same Flatpak installation scope as OBS.

The extension ID is com.obsproject.Studio.Plugin.NTSC_RS, branch stable.
Flatpak mounts it at /app/plugins/NTSC_RS. The library is
/app/plugins/NTSC_RS/lib/obs-plugins/obs-ntsc-rs.so and OBS discovers it through
the merged /app/plugins/lib/obs-plugins directory.
Do not copy files into /var/lib/flatpak, /app, or the OBS settings directory.
The old config-folder plugin method is not the supported OBS Flatpak path.

PRESETS AND SANDBOX
The plugin runs with OBS's existing permissions. It does not add permissions.
Import and export use ordinary file paths, not a plugin-owned document portal.
A path must be visible and writable/readable inside the OBS sandbox.
Use OBS's file chooser to select a file, or use a dedicated presets directory
that is already accessible to OBS. Export to a NEW filename; existing files
are intentionally never overwritten.

The host app settings directory is normally
~/.var/app/com.obsproject.Studio/config/obs-studio, not ~/.config/obs-studio.
Do not put the plugin or test presets in existing profiles or scene collections.
/app is read-only. Paths from the host's /usr or another sandbox's private data
are not generally the same paths inside this sandbox.

If a path is denied, choose an accessible directory. Do not grant unrestricted
home/host access or permanently change OBS permissions just for this plugin.
The automated tests explicitly verify denied access without such overrides.

REMOVE
Close OBS yourself, then (use --system for a system-wide install):
flatpak uninstall --user com.obsproject.Studio.Plugin.NTSC_RS
Never add --delete-data. This removes only the extension, not OBS settings.

LIMITATIONS AND LICENSES
CPU-based, SDR-only; additional variable video latency, no audio delay.
Default processing limit: 480 lines / 30 effect FPS.
OBS or runtime updates can require a rebuild and new compatibility tests.
The bundle contains the plugin, instructions, a data placeholder, and licenses.
Integration: GPL-2.0-or-later. ntsc-rs: MIT option. SIMDe: MIT.
All license notices are under share/licenses/ntsc-rs-obs in the extension.
Matching sources and build scripts must accompany any public distribution.
