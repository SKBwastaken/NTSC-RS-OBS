"""Inspect the final public archives/binaries, not local technical documents."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "dist" / "releases"
VERSION = re.search(r'^version = "([^"]+)"', (ROOT / "Cargo.toml").read_text(), re.M)[1]
PREFIX = f"NTSC-RS-OBS-{VERSION}-Windows"
EXPECTED = {
    "obs-ntsc-rs/bin/64bit/obs-ntsc-rs.dll",
    "obs-ntsc-rs/README.txt",
    "obs-ntsc-rs/LICENSE-GPL-2.0.txt",
    "obs-ntsc-rs/LICENSE-ntsc-rs-MIT.txt",
    "obs-ntsc-rs/THIRD-PARTY.txt",
    "obs-ntsc-rs/data/README.txt",
}


def privacy_check(name, content):
    # Identity comes from local environment, never hard-coded in public tests.
    needles = [str(Path.home()), str(ROOT),
               "\\Users\\", "/Users/", "/home/", "/run/build/", "/github/workspace",
               "/__w/", "Desktop\\", "Desktop/",
               ".pdb", ".env"]
    # A neutral PDB basename can appear in the PE debug directory. PDB files
    # themselves are never part of the payload.
    content = content.replace(b"obs_ntsc_rs.pdb", b"neutral-debug-name")
    for needle in needles:
        if len(needle) < 3:
            continue
        for encoding in ("utf-8", "utf-16-le"):
            assert needle.encode(encoding).lower() not in content.lower(), \
                f"Private path/metadata marker found in {name} ({encoding})"
    username = os.environ.get("USERNAME") or os.environ.get("USER", "")
    if len(username) >= 3:
        # A short username can occur inside generic words (e.g. "Taskbar") or
        # compressed data. Check complete identifier tokens in actual strings.
        strings = [m.group().decode("ascii") for m in re.finditer(rb"[ -~]{3,}", content)]
        strings += [m.group().decode("utf-16-le")
                    for m in re.finditer(rb"(?:[ -~]\x00){3,}", content)]
        identifier = re.compile(r"(?<![\w])" + re.escape(username) + r"(?![\w])", re.I)
        assert not any(identifier.search(s) for s in strings), \
            f"Personal identifier token found in {name}"
    patterns = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"gh[pousr]_[A-Za-z0-9]{30,}",
        rb"github_pat_[A-Za-z0-9_]{30,}",
        rb"AKIA[A-Z0-9]{16}",
        rb"xox[baprs]-[A-Za-z0-9-]{20,}",
        rb'(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*["\'][^"\']{8,}["\']',
    ]
    for pattern in patterns:
        assert not re.search(pattern, content), f"Possible credential found in {name}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-only", action="store_true")
    args = parser.parse_args()
    dll = (ROOT / "target/release/obs_ntsc_rs.dll").read_bytes()
    privacy_check("release DLL", dll)
    with zipfile.ZipFile(RELEASES / f"{PREFIX}.zip") as archive:
        assert set(archive.namelist()) == EXPECTED, "Unexpected ZIP contents"
        assert archive.read("obs-ntsc-rs/bin/64bit/obs-ntsc-rs.dll") == dll
        for entry in archive.infolist():
            privacy_check(entry.filename, archive.read(entry))
            assert not entry.extra and not entry.comment, "Unexpected ZIP metadata"
        assert not archive.comment
    if not args.zip_only:
        exe = (RELEASES / f"{PREFIX}-Setup.exe").read_bytes()
        privacy_check("installer EXE", exe)
        assert exe[:2] == b"MZ"
    expected_assets = {f"{PREFIX}.zip"}
    if not args.zip_only:
        expected_assets.add(f"{PREFIX}-Setup.exe")
    sums = {name: hashlib.sha256((RELEASES / name).read_bytes()).hexdigest()
            for name in expected_assets}
    report = {
        "result": "PASS", "zip_files": sorted(EXPECTED),
        "checks": ["explicit ZIP allowlist", "DLL equality", "UTF-8/UTF-16 personal path scan",
                   "credential pattern scan", "ZIP metadata", "EXE strings"],
        "note": "Heuristic scan, not a mathematical guarantee. Installer payload is also tested separately.",
        "sha256": sums,
    }
    (ROOT / "test-output/package-check.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
