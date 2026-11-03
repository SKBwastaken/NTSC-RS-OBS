# Experimental OBS Flatpak extension

**Status: experimental.** The build, final-bundle audit and automated sandbox
test below pass in GitHub Actions (Ubuntu 24.04, Xvfb, software OpenGL) against
the stable OBS app from Flathub. The manual desktop checklist at the end has not
yet been run: the OBS frontend, file chooser/portal, Wayland, real GPUs, capture
devices and long runs are untested. Existing Windows and Linux system-package
builds remain separate and unchanged.

## Why a separate build

The [official OBS Flatpak guidance](https://github.com/obsproject/obs-studio/discussions/11956)
requires source-built Flatpak extensions using `com.obsproject.Studio` as their
runtime and the SDK used by that OBS deployment. It does not support the old
practice of copying distribution binaries into the app configuration directory.
See also the [upstream manifest](https://github.com/obsproject/obs-studio/blob/master/build-aux/com.obsproject.Studio.json)
and [Flatpak extension documentation](https://docs.flatpak.org/en/latest/extension.html).

At investigation time (2026-11-03), upstream documents
`org.freedesktop.Platform//26.08` and `org.freedesktop.Sdk//26.08`. These are not
silently hard-coded as the selected build runtime: preparation reads the
installed stable OBS metadata, validates its extension endpoint, installs the
matching SDK/Rust extension, and captures exact deployment commits. An unexpected
SDK family or mount layout stops preparation for review.

## Build and test on x86_64 Linux

Use a disposable Linux machine with user namespaces, a session D-Bus, working
Flatpak graphics support, and sufficient space for the OBS app and SDK.
On Ubuntu 24.04 install:

```sh
sudo apt-get update
sudo apt-get install flatpak flatpak-builder ostree binutils python3 xvfb xauth dbus-x11
python3 -m unittest discover -s tests -p 'test_flatpak.py'
python3 packaging/flatpak/build.py prepare
python3 packaging/flatpak/build.py build
```

All Flatpak installs, including the test OBS and extension, use an **isolated**
`FLATPAK_USER_DIR` under `dist/flatpak/installation`. The scripts never launch
your normal OBS frontend, install into your real Flatpak installation, read
profiles/scenes, or set persistent Flatpak permission overrides. Do not run the
scripts as root. Build and install the extension from source; do not substitute
the system Linux ZIP.

`prepare` performs network downloads and writes
`dist/flatpak/runtime-lock.json`. Keep this lock for repeat builds. `build`
refuses changed OBS, Platform, SDK or Rust commits before and after building.
To restore an existing lock in a new isolated installation, copy it to that
path, then run `python3 packaging/flatpak/build.py restore`. Restoration depends
on those commits still being retained by the upstream repository. No floating
update occurs during `build`; SIMDe is pinned to a full Git commit, Cargo
dependencies are vendored/locked and Cargo builds offline.

The deterministic source tar uses an explicit source allowlist, neutral owners
and timestamps. The generated extension manifest uses OBS's installed headers
(`/app/include/obs`) and libobs (`/app/lib`), not Ubuntu headers/libraries.
SIMDe headers are built from pinned source and are not shipped; their license
and per-header copyright/license notices are retained. Rust and C build paths are remapped; release debug symbols are
stripped. Reusing the lock and identical sources controls inputs, but byte-for-byte
reproducibility of the complete OSTree bundle has not been demonstrated.

The separate `.github/workflows/flatpak.yml` runs these steps on Linux.
It does not publish releases or push changes. After every check passes, it keeps
the tested bundle, its report and the audited bundle checkout as a short-lived
workflow artifact for the release review. Workflow logs include the deployment
lock and content hashes in the final report; they are not release assets.
For a locked CI rebuild, supply the saved lock JSON via workflow dispatch.

### Automated runtime checks

The builder compiles a **test-only native executable**, avoiding a dependency on
Python in the runtime. It is never included in the final plugin bundle. After
installing the candidate into the isolated Flatpak installation, tests invoke
that helper via `flatpak run com.obsproject.Studio` **without `--devel`**. This
uses the actual OBS Platform sandbox, not the more permissive SDK environment.
The helper does not launch the frontend or enumerate capture devices.

It checks:

- Plugin discovery from OBS's merged extension directory and successful load.
- Real OpenGL → CPU → GPU color-bar processing, animated output, bypass,
  resolution changes, and continued processing after file errors.
- Preset export/import through actual OBS property callbacks using a Unicode
  filename, saved JSON and imported value validation, and overwrite protection.
- Successful file access in an explicitly granted disposable directory.
- Denied import/export to a synthetic host directory outside the sandbox grants,
  and failed export to read-only `/app`. The host fixture must remain unchanged.
- Clean libobs shutdown before writing a passing report.

The test process temporarily drops host filesystem grants and network access.
It receives only its disposable output directory, the test executable, X11 and
graphics access needed for the test. These are per-process flags, not persistent
permission overrides. Xvfb/software rendering does not establish real desktop,
Wayland, GPU-driver or capture-device compatibility.

### Final candidate and privacy gate

Only after every automated check passes is the candidate copied to
`dist/releases/NTSC-RS-OBS-<version>-Flatpak-x86_64.flatpak`.
`test-output/flatpak-report.json` records the exact lock, input hash, final bundle
hash, payload hashes and sandbox result. Build intermediates and reports remain
local, outside public source/release allowlists. No SHA256SUMS file is created.

Before that copy, the script checks the staged payload, imports the **actual
final bundle** into a temporary OSTree repository, checks out and recursively
audits its real contents and metadata, and compares payload hashes. It scans
binary strings (UTF-8/UTF-16), personal paths and credential patterns, rejects
unexpected payloads/symlinks/debug sections, and retains GPL, ntsc-rs, SIMDe and
Rust dependency notices. These are heuristic privacy checks, not a guarantee.
The source tree/diff, final bundle and all intended accompanying assets still
need a fresh human publication review. Never publish test output, helper
binaries, runtime installations, debug files, or source/build caches.

## Install the tested candidate

Close OBS yourself. For per-user OBS:

```sh
flatpak install --user ./NTSC-RS-OBS-<version>-Flatpak-x86_64.flatpak
flatpak run com.obsproject.Studio
```

For system-installed OBS, use the same scope (`flatpak install --system ...`),
with administrator authorization. Do not install both scopes accidentally.
This is an unsigned local bundle, **not a Flathub submission**. Confirm its
origin when Flatpak asks; never disable signature verification globally.

Extension ID: `com.obsproject.Studio.Plugin.NTSC_RS`, branch `stable`.
Flatpak installs/mounts files, not a custom shell installer:

```text
/app/plugins/NTSC_RS/lib/obs-plugins/obs-ntsc-rs.so
/app/plugins/NTSC_RS/share/obs/obs-plugins/obs-ntsc-rs/
/app/plugins/NTSC_RS/share/licenses/ntsc-rs-obs/
```

OBS sees the merged `lib/obs-plugins` and `share/obs/obs-plugins` directories
under `/app/plugins`. Do not write into `/var/lib/flatpak` deployments or use
`~/.config/obs-studio/plugins` for this build. The app's host settings directory
is normally `~/.var/app/com.obsproject.Studio/config/obs-studio`; it is not an
installation target.

Remove only the extension, without `--delete-data`:

```sh
flatpak uninstall --user com.obsproject.Studio.Plugin.NTSC_RS
```

## Manual desktop release checklist

Run on a disposable Linux account/VM, **not an existing OBS profile**. Install
stable OBS and the tested candidate in that account's normal Flatpak scope.
Record the OBS version, runtime, extension branch and deployment commits with
`flatpak info --show-runtime`, `--show-commit`, and `--show-metadata`.

1. Launch the actual OBS frontend. Create a new, disposable scene with color
   bars or a test image. Add the filter. Confirm visible animated output,
   bypass, processing size changes, and no missing-library errors in the log.
2. In the file chooser, export to a new Unicode filename in a dedicated
   accessible presets directory. Import it and verify an edited setting.
   Attempt exporting again to the same path: content must stay unchanged.
3. Repeat with a JSON file selected through the desktop's file chooser/document
   portal if offered. Confirm both access in this session and behavior after
   restart; do not assume a portal grant persists. Direct path I/O is used by
   the plugin, so not every path returned by a desktop integration is usable.
4. Test a path outside OBS's permissions, plus a read-only destination. Confirm
   a useful failure status and that processing continues without file changes.
   Do not weaken normal OBS permissions to make the test pass.
5. Repeat on Wayland and X11 as available, then exercise realistic resolutions
   and a longer run. Camera/game capture and audio sync are separate checks.
6. Remove only the test extension. Verify the disposable OBS app still starts.

The extension inherits OBS's existing permissions; it cannot grant itself
filesystem access. Never recommend unrestricted host/home access as a plugin
fix. Use an already accessible directory and a new export filename. Public
compatibility claims must name which of the automated and desktop checks
actually ran. An OBS/runtime ABI update requires a rebuild and retest.
