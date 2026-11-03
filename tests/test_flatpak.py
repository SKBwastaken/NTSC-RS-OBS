"""Host-side automation tests; these do NOT establish Flatpak compatibility."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flatpak_build", ROOT / "packaging/flatpak/build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
NOTICE_SPEC = importlib.util.spec_from_file_location(
    "simde_notices", ROOT / "packaging/flatpak/simde_notices.py")
notice_module = importlib.util.module_from_spec(NOTICE_SPEC)
NOTICE_SPEC.loader.exec_module(notice_module)


def lock():
    return {
        "schema": 1, "extension_branch": "stable",
        "app": {"ref": f"app/{build.APP}/x86_64/stable", "commit": "a" * 64},
        "platform": {"ref": "runtime/org.freedesktop.Platform/x86_64/26.08", "commit": "b" * 64},
        "sdk": {"ref": "runtime/org.freedesktop.Sdk/x86_64/26.08", "commit": "c" * 64},
        "rust": {"ref": "runtime/org.freedesktop.Sdk.Extension.rust-stable/x86_64/26.08",
                 "commit": "d" * 64},
    }


class FlatpakAutomationTests(unittest.TestCase):
    def test_lock_accepts_exact_deployments(self):
        build.validate_lock(lock())

    def test_lock_rejects_mixed_branches(self):
        value = lock()
        value["sdk"]["ref"] = value["sdk"]["ref"].replace("26.08", "25.08")
        with self.assertRaises(ValueError):
            build.validate_lock(value)

    def test_lock_rejects_unreviewed_sdk(self):
        value = lock()
        value["sdk"]["ref"] = "runtime/org.kde.Sdk/x86_64/6.8"
        with self.assertRaises(ValueError):
            build.validate_lock(value)

    def test_lock_rejects_floating_commit(self):
        value = lock()
        value["app"]["commit"] = "stable"
        with self.assertRaises(ValueError):
            build.validate_lock(value)

    def test_lock_rejects_beta_or_other_architecture(self):
        for replacement in ("app/com.obsproject.Studio/x86_64/beta",
                            "app/com.obsproject.Studio/aarch64/stable"):
            value = lock()
            value["app"]["ref"] = replacement
            with self.assertRaises(ValueError):
                build.validate_lock(value)

    def test_deployment_drift_stops_build(self):
        with patch.object(build, "info", return_value="0" * 64):
            with self.assertRaisesRegex(RuntimeError, "deployment changed"):
                build.verify_lock(lock())

    def test_parent_metadata_must_match_lock(self):
        value = lock()
        def fake_info(ref, flag):
            if flag == "--show-commit":
                return next(v["commit"] for v in value.values()
                            if isinstance(v, dict) and v["ref"] == ref)
            return ("[Application]\nruntime=org.freedesktop.Platform/x86_64/25.08\n"
                    "sdk=org.freedesktop.Sdk/x86_64/26.08\n")
        with patch.object(build, "info", side_effect=fake_info):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                build.verify_lock(value)

    def test_manifest_uses_obs_sdk_headers_and_pinned_sources(self):
        value = build.manifest(lock(), "f" * 64)
        self.assertEqual(value["runtime"], build.APP)
        self.assertEqual(value["sdk"], "org.freedesktop.Sdk//26.08")
        self.assertTrue(value["build-extension"])
        self.assertNotIn("finish-args", value)
        self.assertEqual(value["build-options"]["env"]["OBS_INCLUDE_DIR"], "/app/include/obs")
        sources = [s for m in value["modules"] for s in m["sources"]]
        self.assertEqual(sources[0]["commit"], build.SIMDE_COMMIT)
        self.assertEqual(sources[-1]["sha256"], "f" * 64)
        self.assertEqual(len(sources[1]["sha256"]), 64)
        self.assertNotIn("Linux.zip", json.dumps(value))

    def test_install_prefix_matches_extension_id(self):
        value = build.manifest(lock(), "f" * 64)
        self.assertEqual(value["id"].rsplit(".", 1)[1], "NTSC_RS")
        self.assertEqual(value["build-options"]["prefix"], "/app/plugins/NTSC_RS")
        self.assertNotIn("libexec", "\n".join(value["modules"][-1]["build-commands"]))

    def test_ostree_audit_checkout_does_not_change_file_ownership(self):
        calls = []
        with patch.object(build, "run", side_effect=lambda *args, **kwargs: calls.append(args)):
            build.checkout_for_audit(Path("repo"), "ref", Path("checkout"))
        self.assertEqual(calls, [("ostree", "--repo=repo", "checkout", "--user-mode",
                                  "ref", "checkout")])

    def test_source_archive_is_deterministic_and_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ["Cargo.toml", "Cargo.lock", "build.rs", ".cargo/config.toml",
                     "packaging/README-Flatpak.txt", "packaging/THIRD-PARTY.txt",
                     "packaging/data/README.txt", "tests/flatpak_smoke.c", "src/lib.rs",
                     "native/filter.c", "vendor/notice.txt", "vendor/cc/src/target/parser.rs",
                     "AGENTS.md", "HANDOFF.md",
                     "dist/private.txt", "test-output/private.json", ".env"]
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
            with patch.object(build, "ROOT", root):
                first = build.source_archive(root / "first.tar")
                second = build.source_archive(root / "second.tar")
            self.assertEqual(first, second)
            with tarfile.open(root / "first.tar") as archive:
                entries = archive.getmembers()
                self.assertEqual(len(entries), 12)
                self.assertTrue(all(e.uid == e.gid == e.mtime == 0 for e in entries))
                self.assertFalse(any("private" in e.name or e.name.endswith(".env") for e in entries))
                self.assertIn("source/vendor/cc/src/target/parser.rs", archive.getnames())

    def test_payload_rejects_unexpected_file(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "unexpected.txt").write_text("not permitted")
            with self.assertRaisesRegex(RuntimeError, "payload files"):
                build.audit_tree(Path(temp))

    def test_payload_requires_all_licenses(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "payload files"):
                build.audit_tree(Path(temp))
        self.assertIn("share/licenses/ntsc-rs-obs/LICENSE-SIMDe.txt", build.PAYLOAD)

    def test_payload_rejects_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in build.PAYLOAD:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"license or data")
            with self.assertRaisesRegex(RuntimeError, "x86_64 ELF"):
                build.audit_tree(root)

    def test_metadata_rejects_additional_permissions(self):
        text = (f"[Runtime]\nname={build.EXT}\n[ExtensionOf]\n"
                f"ref=app/{build.APP}/x86_64/stable\n"
                "runtime=org.freedesktop.Platform/x86_64/26.08\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "metadata"
            path.write_text(text)
            build.audit_metadata(path, lock())
            path.write_text(text + "[Context]\nfilesystems=host;\n")
            with self.assertRaisesRegex(RuntimeError, "extra permissions"):
                build.audit_metadata(path, lock())
            path.write_text(text.replace("26.08", "25.08"))
            with self.assertRaisesRegex(RuntimeError, "different Platform"):
                build.audit_metadata(path, lock())

    def test_test_runs_without_sdk_or_persistent_permission_override(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            helper = work / "helper"
            def fake_run(*args, **kwargs):
                calls.append(args)
                (work / "sandbox/report.json").write_text('{"result":"PASS"}')
            with patch.object(build, "run", side_effect=fake_run):
                build.sandbox_test(helper, work)
        command = calls[0]
        self.assertIn("--nofilesystem=host:reset", command)
        self.assertIn("--unshare=network", command)
        self.assertNotIn("--devel", command)
        self.assertNotIn("override", command)
        self.assertNotIn("--filesystem=home", command)
        self.assertEqual(command[-3], build.APP)

    def test_linux_private_paths_are_rejected_in_binary_strings(self):
        for marker in (b"/home/private/build", b"/run/build/project/src", b"/github/workspace"):
            with self.assertRaises(AssertionError):
                build.privacy_check("fixture ELF", b"\x7fELF" + marker)

    def test_isolated_installation_never_targets_user_obs(self):
        env = build.environment()
        self.assertEqual(env["FLATPAK_USER_DIR"], str(build.STATE / "installation"))
        self.assertTrue(build.STATE.is_relative_to(ROOT / "dist"))

    def test_simde_notices_preserve_all_blocks_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            notice = "/* Copyright Example contributor. Permission granted. */"
            (root / "a.h").write_text(notice + "\n#define SOMETHING 1\n"
                                      "// SPDX-License-Identifier: MIT\n"
                                      "/* Copyright Another contributor */")
            (root / "b.h").write_text(notice)
            text = notice_module.notices(root)
            self.assertEqual(text.count(notice), 1)
            self.assertIn("Another contributor", text)
            self.assertIn("SPDX-License-Identifier: MIT", text)

    def test_empty_simde_notice_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):
                notice_module.notices(Path(temp))


if __name__ == "__main__":
    unittest.main()
