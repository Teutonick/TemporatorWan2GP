"""Regression tests for temporary sessions and the WanGP integration contract."""

import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from threading import RLock
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows file locking")
class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.env = dict(os.environ, TEMP=self.temp, TMP=self.temp, PYTHONDONTWRITEBYTECODE="1")

    def run_script(self, source):
        return subprocess.run(
            [sys.executable, "-c", source], cwd=ROOT, env=self.env,
            capture_output=True, text=True, timeout=15,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_normal_exit_and_environment(self):
        self.assert_success(self.run_script("""
import os, tempfile
from pathlib import Path
from session import open_temporary_session
root = open_temporary_session(Path.cwd())
assert Path(tempfile.gettempdir()) == root / "temp"
assert Path(os.environ["GRADIO_TEMP_DIR"]) == root / "gradio"
(root / "temp" / "preview.mp4").write_bytes(b"preview")
"""))
        self.assertEqual(list(Path(self.temp).glob("*/session-*")), [])

    def test_crash_cleanup_preserves_unrelated_files(self):
        result = self.run_script("""
import os
from pathlib import Path
from session import open_temporary_session
root = open_temporary_session(Path.cwd())
(root.parent / "keep.txt").touch()
(root / "temp" / "unsaved.mp4").touch()
os._exit(42)
""")
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual(len(list(Path(self.temp).glob("*/session-*/temp/unsaved.mp4"))), 1)
        self.assert_success(self.run_script("""
from pathlib import Path
from session import open_temporary_session
root = open_temporary_session(Path.cwd())
assert not list(root.parent.glob("session-*/temp/unsaved.mp4"))
assert (root.parent / "keep.txt").is_file()
"""))
        self.assertEqual(list(Path(self.temp).glob("*/session-*")), [])

    def test_second_process_cannot_clean_live_session(self):
        self.assert_success(self.run_script("""
import os, subprocess, sys
from pathlib import Path
from session import open_temporary_session
original_env = os.environ.copy()
root = open_temporary_session(Path.cwd())
child = subprocess.run([sys.executable, "-c",
    "from pathlib import Path; from session import open_temporary_session; "
    "open_temporary_session(Path.cwd())"], capture_output=True, text=True, env=original_env,
    timeout=10)
assert child.returncode != 0 and "Another Temporator instance" in child.stderr, child.stderr
assert root.exists()
"""))


class AddonTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        directory = self.root / "owned" / "session"
        directory.mkdir(parents=True)
        source = SimpleNamespace(
            id="video", files_key="files", selected_key="selected", settings_key="settings",
        )

        package = ModuleType("test_temporator")
        package.__path__ = [str(ROOT)]
        self.host_storage = SimpleNamespace(
            OUTPUT_KEYS=("save_path", "image_save_path", "audio_save_path", "mesh_save_path"),
            output_config=Mock(side_effect=lambda config, *, state: config),
            bundle_files=Mock(side_effect=lambda path: {path.suffix: path}),
            copy_bundle=Mock(side_effect=lambda path, destination: (str(destination / path.name), [])),
        )
        self.enterContext(patch.dict(sys.modules, {
            "test_temporator": package,
            "shared": ModuleType("shared"),
            "shared.utils": ModuleType("shared.utils"),
            "shared.utils.workspace_storage": self.host_storage,
            "shared.utils.gallery_sources": SimpleNamespace(
                GALLERY_SOURCES=(source,), SOURCES={source.id: source},
            ),
            "shared.utils.plugins": SimpleNamespace(WAN2GPPlugin=object),
            "gradio": ModuleType("gradio"),
        }))
        module = importlib.import_module("test_temporator.plugin")
        self.session = module.MediaSession(directory)
        self.addon = module.TemporatorPlugin()
        self.addon.session = self.session
        self.addon.get_gen_info = lambda state: state
        self.addon.gallery_choice = lambda gen, source: gen[source.selected_key]
        self.addon.lock = RLock()
        self.result = self.session.outputs / "preview.png"
        self.result.write_bytes(b"preview")

    def test_queue_and_debug_outputs_stay_in_session(self):
        ram_report = Mock()
        vram_report = Mock()
        host = {"write_ram_debug_report": ram_report, "write_vram_debug_report": vram_report}
        self.session.install_host_paths(host)
        self.assertEqual(Path(host["AUTOSAVE_PATH"]), self.session.directory / "queue.zip")
        self.assertEqual(host["AUTOSAVE_TEMPLATE_PATH"], host["AUTOSAVE_PATH"])
        self.assertEqual(Path(host["AUTOSAVE_ERROR_FILENAME"]), self.session.directory / "error_queue.zip")
        host["write_ram_debug_report"]("persistent", "label", census_label="generation")
        host["write_vram_debug_report"]("persistent", "label")
        ram_report.assert_called_once_with(str(self.session.directory), "label", census_label="generation")
        vram_report.assert_called_once_with(str(self.session.directory), "label")

    def test_filter_keeps_persistent_media_and_metadata_aligned(self):
        existing = self.root / "saved.png"
        gallery = {"files": [str(self.result), str(existing)], "settings": ["temporary", "saved"], "selected": 1}
        self.assertEqual(self.session.without_temporary_media(gallery), {
            "files": [str(existing)], "settings": ["saved"], "selected": 0,
        })
        self.assertEqual(gallery["selected"], 1)
        self.assertEqual(len(gallery["files"]), 2)

    def test_save_candidate_requires_finished_selected_session_media(self):
        state = {"current_gallery_source": "video", "files": [str(self.result)], "selected": 0}
        self.assertEqual(self.addon.candidate(state), self.result)
        self.assertIsNone(self.addon.candidate({**state, "in_progress": True}))
        self.assertIsNone(self.addon.candidate({**state, "selected": -1}))
        self.assertIsNone(self.addon.candidate({**state, "settings": [{"output_role": "intermediate"}]}))
        self.result.unlink()
        self.assertIsNone(self.addon.candidate(state))

    def test_export_uses_original_destination_only_on_save(self):
        destination = self.root / "persistent"
        state = object()
        config = {"image_save_path": str(destination)}
        self.host_storage.copy_bundle.assert_not_called()
        result = self.session.save_result(self.result, config, "image_save_path", state)
        self.host_storage.output_config.assert_called_once_with(config, state=state)
        self.host_storage.copy_bundle.assert_called_once_with(self.result, destination)
        self.assertEqual(result, str(destination / self.result.name))

    def test_export_rejects_outside_source_and_companion(self):
        outside = self.root / "outside.png"
        outside.touch()
        with self.assertRaisesRegex(ValueError, "temporary session"):
            self.session.save_result(outside, {}, "save_path", None)
        self.host_storage.bundle_files.side_effect = None
        self.host_storage.bundle_files.return_value = {".png": self.result, ".json": outside}
        with self.assertRaisesRegex(ValueError, "companion"):
            self.session.save_result(self.result, {}, "save_path", None)
        self.host_storage.copy_bundle.assert_not_called()

    def test_export_rejects_destination_in_session(self):
        with self.assertRaisesRegex(ValueError, "output folder"):
            self.session.save_result(
                self.result, {"save_path": str(self.session.directory)}, "save_path", None,
            )
        self.host_storage.copy_bundle.assert_not_called()


class MetadataTests(unittest.TestCase):
    def test_manifest_matches_distribution_and_changelog(self):
        metadata = json.loads((ROOT / "plugin_info.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["name"], "TemporatorWan2GP")
        self.assertEqual(metadata["type"], ["extension"])
        self.assertEqual(metadata["url"], "https://github.com/Teutonick/TemporatorWan2GP")
        self.assertRegex(metadata["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(metadata["date"], r"^\d{4}-\d{2}-\d{2}$")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
        self.assertRegex(changelog, rf"(?m)^## {re.escape(metadata['version'])}$")
        for name in ("__init__.py", "plugin.py", "LICENSE"):
            self.assertTrue((ROOT / name).is_file(), name)


