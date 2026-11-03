"""Build a source-based OBS extension in an isolated Flatpak user installation.

No remote publication, host OBS launch, profile access, or permission overrides.
Run `prepare` once to capture a lock; `build` requires those exact deployments.
"""
import argparse
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from package_check import privacy_check  # noqa: E402

APP = "com.obsproject.Studio"
EXT = APP + ".Plugin.NTSC_RS"
PREFIX = "/app/plugins/NTSC_RS"
SIMDE_COMMIT = "71fd833d9666141edcd1d3c109a80e228303d8d7"
STATE = ROOT / "dist/flatpak"
LOCK = STATE / "runtime-lock.json"
LICENSE_DIR = "share/licenses/ntsc-rs-obs"
PAYLOAD = {
    "lib/obs-plugins/obs-ntsc-rs.so",
    "share/obs/obs-plugins/obs-ntsc-rs/README.txt",
    "share/doc/ntsc-rs-obs/README.txt",
    f"{LICENSE_DIR}/LICENSE-GPL-2.0.txt",
    f"{LICENSE_DIR}/LICENSE-ntsc-rs-MIT.txt",
    f"{LICENSE_DIR}/LICENSE-SIMDe.txt",
    f"{LICENSE_DIR}/SIMDe-NOTICES.txt",
    f"{LICENSE_DIR}/THIRD-PARTY.txt",
}


def run(*args, cwd=None, capture=False, env=None, timeout=None):
    result = subprocess.run(args, cwd=cwd, env=env or environment(), check=True,
                            text=True, stdout=subprocess.PIPE if capture else None,
                            timeout=timeout)
    return result.stdout.strip() if capture else None


def environment():
    env = os.environ.copy()
    # Never install/remove plugins or update OBS in the real user installation.
    env["FLATPAK_USER_DIR"] = str(STATE / "installation")
    return env


def metadata(text):
    result = configparser.ConfigParser(interpolation=None)
    result.read_string(text)
    return result


def info(ref, flag):
    return run("flatpak", "info", "--user", flag, ref, capture=True)


def checkout_for_audit(repo, ref, destination):
    # The unprivileged CI runner cannot chown files to the OSTree-stored owner.
    run("ostree", f"--repo={repo}", "checkout", "--user-mode", ref, str(destination))


def validate_lock(lock):
    if lock.get("schema") != 1 or lock.get("extension_branch") != "stable":
        raise ValueError("Unsupported Flatpak lock")
    expected = {
        "app": rf"app/{re.escape(APP)}/x86_64/stable",
        "platform": r"runtime/org\.freedesktop\.Platform/x86_64/[\w.-]+",
        "sdk": r"runtime/org\.freedesktop\.Sdk/x86_64/[\w.-]+",
        "rust": r"runtime/org\.freedesktop\.Sdk\.Extension\.rust-stable/x86_64/[\w.-]+",
    }
    for key, pattern in expected.items():
        item = lock[key]
        if not re.fullmatch(pattern, item["ref"]):
            raise ValueError(f"Unexpected {key} ref")
        if not re.fullmatch(r"[a-f0-9]{64}", item["commit"]):
            raise ValueError(f"Invalid {key} commit")
    branches = {lock[k]["ref"].rsplit("/", 1)[1] for k in ("platform", "sdk", "rust")}
    if len(branches) != 1:
        raise ValueError("SDK, platform and Rust extension branches differ")


def deployment(ref):
    return {"ref": ref, "commit": info(ref, "--show-commit")}


def prepare():
    if LOCK.exists():
        raise RuntimeError("Lock already exists. Keep it for rebuilds; use a fresh checkout to select new runtimes.")
    run("flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
        "https://flathub.org/repo/flathub.flatpakrepo")
    app = f"app/{APP}/x86_64/stable"
    run("flatpak", "install", "--user", "--noninteractive", "flathub", app)
    app_meta = metadata(info(app, "--show-metadata"))
    sdk = app_meta["Application"]["sdk"]
    runtime = app_meta["Application"]["runtime"]
    # Refuse an unreviewed upstream runtime migration instead of guessing an SDK.
    if not sdk.startswith("org.freedesktop.Sdk/x86_64/"):
        raise RuntimeError("OBS SDK changed; review the upstream manifest before building.")
    branch = sdk.rsplit("/", 1)[1]
    endpoint = app_meta[f"Extension {APP}.Plugin"]
    if "stable" not in endpoint.get("versions", endpoint.get("version", "")).split(";"):
        raise RuntimeError("OBS no longer accepts the stable plugin branch")
    if endpoint["directory"] != "plugins" or not endpoint.getboolean("subdirectories"):
        raise RuntimeError("OBS plugin mount layout changed")
    if "lib/obs-plugins" not in endpoint["merge-dirs"].split(";"):
        raise RuntimeError("OBS plugin discovery layout changed")
    rust = f"org.freedesktop.Sdk.Extension.rust-stable/x86_64/{branch}"
    run("flatpak", "install", "--user", "--noninteractive", "flathub", sdk, rust)
    lock = {
        "schema": 1, "extension_branch": "stable",
        "app": deployment(app), "platform": deployment("runtime/" + runtime),
        "sdk": deployment("runtime/" + sdk), "rust": deployment("runtime/" + rust),
    }
    validate_lock(lock)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print("Captured exact OBS, platform, SDK and Rust deployment commits.")


def verify_lock(lock):
    validate_lock(lock)
    for key in ("app", "platform", "sdk", "rust"):
        item = lock[key]
        if info(item["ref"], "--show-commit") != item["commit"]:
            raise RuntimeError(f"{key} deployment changed; restore the locked commit before rebuilding")
    app = metadata(info(lock["app"]["ref"], "--show-metadata"))
    for key, field in (("platform", "runtime"), ("sdk", "sdk")):
        if "runtime/" + app["Application"][field] != lock[key]["ref"]:
            raise RuntimeError("Locked SDK/platform does not match the locked OBS deployment")


def restore():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    validate_lock(lock)
    run("flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
        "https://flathub.org/repo/flathub.flatpakrepo")
    for key in ("platform", "sdk", "rust", "app"):
        item = lock[key]
        run("flatpak", "install", "--user", "--noninteractive", "--no-deps",
            "--no-related", "flathub", item["ref"])
        run("flatpak", "update", "--user", "--noninteractive", "--no-deps",
            "--no-related", "--commit=" + item["commit"], item["ref"])
    verify_lock(lock)


def source_archive(destination):
    # Fixed allowlist, not a recursive copy of the working directory.
    files = [ROOT / name for name in ("Cargo.toml", "Cargo.lock", "build.rs",
             ".cargo/config.toml", "packaging/README-Flatpak.txt",
             "packaging/THIRD-PARTY.txt", "packaging/data/README.txt",
             "tests/flatpak_smoke.c")]
    for directory in ("src", "native", "vendor"):
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    with tarfile.open(destination, "w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(files):
            if path.is_symlink():
                raise RuntimeError("Source symlinks are not permitted")
            name = path.relative_to(ROOT).as_posix()
            # cc's vendored src/target is source code, not a Cargo output folder.
            if any(p in {"__pycache__", ".git"} for p in path.relative_to(ROOT).parts):
                raise RuntimeError("Unexpected generated source")
            entry = tarfile.TarInfo("source/" + name)
            data = path.read_bytes()
            entry.size, entry.mode = len(data), 0o644
            entry.uid = entry.gid = entry.mtime = 0
            archive.addfile(entry, io.BytesIO(data))
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def manifest(lock, source_hash):
    sdk_ref = lock["sdk"]["ref"].split("/")
    sdk = sdk_ref[1] + "//" + sdk_ref[3]
    return {
        "id": EXT, "branch": "stable", "runtime": APP, "runtime-version": "stable",
        "sdk": sdk, "sdk-extensions": ["org.freedesktop.Sdk.Extension.rust-stable"],
        "build-extension": True, "separate-locales": False, "appstream-compose": False,
        "build-options": {
            "prefix": PREFIX, "strip": True,
            "prepend-path": "/usr/lib/sdk/rust-stable/bin",
            "env": {
                "CARGO_NET_OFFLINE": "true", "CARGO_HOME": "/tmp/cargo-home",
                "CARGO_PROFILE_RELEASE_STRIP": "symbols",
                "OBS_INCLUDE_DIR": "/app/include/obs", "OBS_LIB_DIR": "/app/lib",
                "RUSTFLAGS": "--remap-path-prefix=/run/build=ntsc-rs-obs",
                "CFLAGS": "-ffile-prefix-map=/run/build=ntsc-rs-obs",
                "SOURCE_DATE_EPOCH": "0",
            },
        },
        "modules": [
            {
                "name": "simde", "buildsystem": "simple",
                "build-commands": [
                    'mkdir -p "${FLATPAK_DEST}/include"',
                    'cp -R simde "${FLATPAK_DEST}/include/"',
                    f'install -Dm644 COPYING "${{FLATPAK_DEST}}/{LICENSE_DIR}/LICENSE-SIMDe.txt"',
                    f'python3 simde_notices.py simde "${{FLATPAK_DEST}}/{LICENSE_DIR}/SIMDe-NOTICES.txt"',
                ],
                "cleanup": ["/include"],
                "sources": [
                    {"type": "git", "url": "https://github.com/simd-everywhere/simde.git",
                     "commit": SIMDE_COMMIT},
                    {"type": "file", "path": "simde_notices.py",
                     "sha256": hashlib.sha256((ROOT / "packaging/flatpak/simde_notices.py").read_bytes()).hexdigest()},
                ],
            },
            {
                "name": "ntsc-rs", "buildsystem": "simple",
                "build-commands": [
                    'test -f /app/include/obs/obs.h',
                    'export CFLAGS="$CFLAGS -I${FLATPAK_DEST}/include"; '
                    'cargo test --release --locked --offline && cargo build --release --locked --offline',
                    # Test helper stays in the build tree, never in the extension payload.
                    # Newer OBS headers deprecate APIs this standalone harness still needs.
                    'cc -std=gnu11 -O2 -Wall -Wextra -Werror -Wno-error=deprecated-declarations '
                    '-I/app/include/obs -I"${FLATPAK_DEST}/include" '
                    'tests/flatpak_smoke.c -L/app/lib -Wl,-rpath,/app/lib '
                    '-l:libobs.so.0 -lX11 -lpthread -o flatpak-smoke',
                    'install -Dm755 target/release/libobs_ntsc_rs.so '
                    '"${FLATPAK_DEST}/lib/obs-plugins/obs-ntsc-rs.so"',
                    'install -Dm644 packaging/data/README.txt '
                    '"${FLATPAK_DEST}/share/obs/obs-plugins/obs-ntsc-rs/README.txt"',
                    'install -Dm644 packaging/README-Flatpak.txt '
                    '"${FLATPAK_DEST}/share/doc/ntsc-rs-obs/README.txt"',
                    f'install -Dm644 vendor/obs-studio/COPYING "${{FLATPAK_DEST}}/{LICENSE_DIR}/LICENSE-GPL-2.0.txt"',
                    f'install -Dm644 vendor/ntsc-rs/LICENSE-MIT "${{FLATPAK_DEST}}/{LICENSE_DIR}/LICENSE-ntsc-rs-MIT.txt"',
                    f'install -Dm644 packaging/THIRD-PARTY.txt "${{FLATPAK_DEST}}/{LICENSE_DIR}/THIRD-PARTY.txt"',
                ],
                "sources": [{"type": "archive", "path": "source.tar", "sha256": source_hash}],
            },
        ],
    }


def audit_tree(tree):
    actual = set()
    for path in tree.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("Symlink in extension payload")
        if not path.is_file():
            continue
        name = path.relative_to(tree).as_posix()
        actual.add(name)
        privacy_check(name, path.read_bytes())
    # flatpak-builder records its resolved source manifest as manifest.json.
    if actual - PAYLOAD - {"manifest.json"} or not PAYLOAD <= actual:
        raise RuntimeError("Unexpected or missing extension payload files")
    lib = tree / "lib/obs-plugins/obs-ntsc-rs.so"
    data = lib.read_bytes()
    if (data[:6] != b"\x7fELF\x02\x01" or int.from_bytes(data[18:20], "little") != 62
            or int.from_bytes(data[16:18], "little") != 3):
        raise RuntimeError("Expected an x86_64 ELF library")
    sections = run("readelf", "--wide", "--sections", str(lib), capture=True)
    if re.search(r"\.(?:z?debug|gnu_debuglink)", sections):
        raise RuntimeError("Debug sections in release payload")
    return {name: hashlib.sha256((tree / name).read_bytes()).hexdigest()
            for name in sorted(actual)}


def audit_metadata(path, lock):
    data = metadata(path.read_text(encoding="utf-8"))
    if data["Runtime"]["name"] != EXT:
        raise RuntimeError("Unexpected extension identity")
    if data["ExtensionOf"]["ref"] != lock["app"]["ref"]:
        raise RuntimeError("Extension targets a different OBS app")
    if "runtime/" + data["ExtensionOf"]["runtime"] != lock["platform"]["ref"]:
        raise RuntimeError("Extension targets a different Platform")
    for section in ("Context", "Session Bus Policy", "System Bus Policy", "Extra Data"):
        if data.has_section(section) and any(data[section].values()):
            raise RuntimeError("Extension must not request extra permissions or downloads")


def sandbox_test(helper, work):
    output = work / "sandbox"
    output.mkdir()
    # Denied directory is a synthetic fixture outside all granted paths.
    denied = work / "denied"
    denied.mkdir()
    (denied / "preset.json").write_text('{"version":1,"luma_smear":0.5}', encoding="utf-8")
    # No --devel: this runs against the real Platform, not the SDK.
    run("xvfb-run", "-a", "-s", "-screen 0 1280x720x24",
        "flatpak", "run", "--user", "--arch=x86_64", "--branch=stable",
        "--unshare=network", "--nosocket=wayland", "--socket=x11",
        "--nofilesystem=host:reset", f"--filesystem={output}:rw",
        f"--filesystem={helper}:ro", "--env=LIBGL_ALWAYS_SOFTWARE=1",
        "--env=XDG_CONFIG_HOME=/tmp/ntsc-rs-test-config",
        "--env=XDG_DATA_HOME=/tmp/ntsc-rs-test-data",
        "--env=XDG_CACHE_HOME=/tmp/ntsc-rs-test-cache",
        f"--command={helper}", APP, str(output), str(denied), timeout=180)
    report = json.loads((output / "report.json").read_text())
    if report["result"] != "PASS":
        raise RuntimeError("Flatpak sandbox test did not pass")
    if (denied / "preset.json").read_text() != '{"version":1,"luma_smear":0.5}':
        raise RuntimeError("Denied host fixture was modified")
    return report


def build():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    verify_lock(lock)
    STATE.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=STATE))
    source_hash = source_archive(work / "source.tar")
    shutil.copyfile(ROOT / "packaging/flatpak/simde_notices.py", work / "simde_notices.py")
    spec = work / "extension.json"
    spec.write_text(json.dumps(manifest(lock, source_hash), indent=2) + "\n", encoding="utf-8")
    repo, tree = work / "repo", work / "build"
    # Keep build dirs: the test-only helper is taken from there, never from the payload.
    run("flatpak-builder", "--user", "--arch=x86_64", "--disable-rofiles-fuse", "--keep-build-dirs",
        f"--repo={repo}", str(tree), str(spec), cwd=work)
    # Ensure the build did not resolve different deployments mid-run.
    verify_lock(lock)
    helpers = list((work / ".flatpak-builder/build").glob("ntsc-rs-*/flatpak-smoke"))
    if len(helpers) != 1:
        raise RuntimeError("Cannot locate the isolated native test helper")
    helper = work / "flatpak-smoke"
    shutil.copyfile(helpers[0], helper)
    helper.chmod(0o755)
    staged_hashes = audit_tree(tree / "files")
    version = re.search(r'^version = "([^"]+)"', (ROOT / "Cargo.toml").read_text(), re.M)[1]
    # Keep the bundle private until its imported payload and real sandbox test pass.
    candidate = work / f"NTSC-RS-OBS-{version}-Flatpak-x86_64.flatpak"
    run("flatpak", "build-bundle", "--runtime", "--arch=x86_64", str(repo),
        str(candidate), EXT, "stable")
    imported, checkout = work / "imported", work / "checkout"
    run("ostree", f"--repo={imported}", "init", "--mode=archive")
    run("flatpak", "build-import-bundle", str(imported), str(candidate))
    ref = f"runtime/{EXT}/x86_64/stable"
    checkout_for_audit(imported, ref, checkout)
    final_hashes = audit_tree(checkout / "files")
    audit_metadata(checkout / "metadata", lock)
    if final_hashes != staged_hashes:
        raise RuntimeError("Final bundle payload differs from audited build")
    for path in checkout.rglob("*"):
        if path.is_file():
            privacy_check(path.relative_to(checkout).as_posix(), path.read_bytes())
    privacy_check(candidate.name, candidate.read_bytes())
    run("flatpak", "install", "--user", "--noninteractive", "--reinstall", "--no-deps",
        "--no-related", "--no-gpg-verify", str(candidate))
    sandbox_report = sandbox_test(helper, work)
    verify_lock(lock)
    releases = ROOT / "dist/releases"
    releases.mkdir(parents=True, exist_ok=True)
    destination = releases / candidate.name
    shutil.copyfile(candidate, destination)
    report = {
        "result": "PASS", "bundle": destination.name, "lock": lock,
        "source_sha256": source_hash, "payload_sha256": final_hashes,
        "bundle_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "sandbox": sandbox_report,
        "scope": "Isolated libobs in real OBS Flatpak runtime; no frontend/portal GUI verification",
    }
    out = ROOT / "test-output"
    out.mkdir(exist_ok=True)
    (out / "flatpak-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "restore", "build"))
    args = parser.parse_args()
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "AMD64"}:
        parser.error("Requires x86_64 Linux with Flatpak, flatpak-builder, OSTree, binutils and Xvfb")
    if os.geteuid() == 0:
        parser.error("Run as an ordinary user, not root")
    required = ("flatpak",) if args.action != "build" else (
        "flatpak", "flatpak-builder", "ostree", "readelf", "xvfb-run")
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        parser.error("Missing tools: " + ", ".join(missing))
    if args.action == "prepare":
        prepare()
    elif args.action == "restore":
        restore()
    else:
        build()


if __name__ == "__main__":
    main()
