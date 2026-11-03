"""Exercise installer file/update/uninstall logic in an isolated no-registry build."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-output" / "packaging"
COMPILER = Path(os.environ["LOCALAPPDATA"]) / "Programs/Inno Setup 6/ISCC.exe"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(COMPILER), "/DTestInstall=1", str(ROOT / "packaging/installer.iss")],
                   check=True)
    setup = OUT / "installer-test.exe"
    destination = OUT / ("install-" + uuid.uuid4().hex)
    args = [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
            f"/DIR={destination}", f"/LOG={OUT / 'install.log'}"]
    subprocess.run(args, check=True, timeout=60)
    expected = (ROOT / "target/release/obs_ntsc_rs.dll").read_bytes()
    dll = destination / "bin/64bit/obs-ntsc-rs.dll"
    assert dll.read_bytes() == expected
    from package_check import EXPECTED, privacy_check
    for entry in EXPECTED:
        relative = entry.removeprefix("obs-ntsc-rs/")
        installed = (destination / relative).read_bytes()
        assert installed == (ROOT / "dist/obs-ntsc-rs" / relative).read_bytes()
        privacy_check("decompressed installer payload: " + relative, installed)
    # Run again to exercise an installer-managed update.
    subprocess.run(args, check=True, timeout=60)
    assert dll.read_bytes() == expected
    sentinel = destination / "unrelated-user-file.txt"
    sentinel.write_text("This test-owned sentinel must survive uninstall.")
    uninstaller = destination / "uninstall/unins000.exe"
    assert uninstaller.exists()
    subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    f"/LOG={OUT / 'uninstall.log'}"], check=True, timeout=60)
    assert not dll.exists(), "Plugin DLL was not removed"
    assert sentinel.exists(), "Uninstaller removed an unrelated file"
    # A conflicting manual DLL must not be overwritten.
    conflict = OUT / ("conflict-" + uuid.uuid4().hex)
    conflict_dll = conflict / "bin/64bit/obs-ntsc-rs.dll"
    conflict_dll.parent.mkdir(parents=True)
    conflict_dll.write_bytes(b"test-owned manual DLL sentinel")
    result = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                             "/NORESTART", "/SP-", f"/DIR={conflict}",
                             f"/LOG={OUT / 'conflict.log'}"], timeout=60)
    assert result.returncode != 0
    assert conflict_dll.read_bytes() == b"test-owned manual DLL sentinel"
    report = {
        "result": "PASS", "mode": "same file logic, no elevation/registry; OBS gate bypassed only in test build",
        "checks": ["isolated install", "decompressed payload equality and privacy", "installer-managed update",
                   "uninstall", "unrelated file preserved", "manual DLL conflict refused"],
        "dll_sha256": hashlib.sha256(expected).hexdigest(),
        "note": "Production UAC flow is not executed; no real OBS installation is changed.",
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
