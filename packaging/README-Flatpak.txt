NTSC-RS for OBS, Flatpak extension (x86_64)

STATUS AND DISCLAIMER
Experimental build path. Flatpak compatibility has NOT been verified on the
development machine (Windows without Linux/Flatpak). Do not treat the existence
of build scripts as proof of compatibility. A candidate is copied into
dist/releases only after its automated real-runtime sandbox test passes.
Desktop GUI, file chooser/portal, Wayland, and long-duration tests are separate
manual release checks. This is a vibe-coded proof of concept. Use at your own risk.

REQUIREMENTS
- OBS Studio 32+ from Flathub, app ID com.obsproject.Studio, stable, x86_64.
- A Flatpak bundle built for the matching OBS and runtime deployment.
  See the accompanying local build report/lock for exact commits.
- Do not use the Linux system-package ZIP with Flatpak, or this bundle with
  system-package OBS. Snap is not supported.

INSTALL (only after the candidate has been tested)
1. Close Flatpak OBS yourself. The installer never stops OBS.
2. Install the locally downloaded bundle:
   flatpak install --user ./NTSC-RS-OBS-<version>-Flatpak-x86_64.flatpak
3. Start OBS as usual: flatpak run com.obsproject.Studio
4. Source > Filters > Effect Filters > + > ntsc-rs (NTSC / VHS).

This is a local, unsigned bundle, not a Flathub listing or an automatic updater.
Verify its origin. Do not add a permanent remote or disable signature checks
globally. Use the same Flatpak installation scope as OBS; the documented path
assumes a per-user OBS installation. Consult the full guide for system scope.

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
Close OBS yourself, then:
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
