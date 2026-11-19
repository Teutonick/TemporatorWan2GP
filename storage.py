"""Storage routing and explicit bundle export for Wan2GP's generation galleries."""

from pathlib import Path
from functools import wraps
import sys

from shared.utils import workspace_storage
from shared.utils.gallery_sources import GALLERY_SOURCES


class MediaSession:
    def __init__(self, directory):
        self.directory = directory.resolve(strict=True)
        self.outputs = self.directory / "outputs"
        self.outputs.mkdir()
        self.original_output_config = workspace_storage.output_config

    def contains(self, path):
        return Path(path).resolve().is_relative_to(self.directory)

    def install(self):
        from shared.deepy import workspaces as deepy_workspaces
        from shared.utils import workspaces

        WorkspaceStore = workspaces.WorkspaceStore

        def temporary_output_config(config, *, state=None, binding=None):
            return {**config, **dict.fromkeys(workspace_storage.OUTPUT_KEYS, str(self.outputs))}

        workspace_storage.output_config = temporary_output_config
        # Some host modules import the function directly before plugin initialization.
        for name in ("shared.deepy.workspaces", "shared.mcp.workspaces"):
            module = sys.modules.get(name)
            if module is not None and getattr(module, "output_config", None) is self.original_output_config:
                module.output_config = temporary_output_config

        original_save = WorkspaceStore.save
        original_load = workspaces.load_gallery
        original_adopt = WorkspaceStore.adopt
        live_galleries = {}

        @wraps(original_save)
        def save_gallery(store, workspace_id, gallery, **kwargs):
            filtered = self.without_temporary_media(gallery)
            with store.lock:
                changed = original_save(store, workspace_id, filtered, **kwargs)
                if gallery != filtered:
                    record = store.get(workspace_id)
                    live_galleries[workspace_id] = (record["gallery"], gallery)
                else:
                    live_galleries.pop(workspace_id, None)
                return changed

        @wraps(original_load)
        def load_gallery(record, read_settings):
            live = live_galleries.get(record.get("id"))
            if live is not None and record["gallery"] == live[0]:
                record = {**record, "gallery": live[1]}
            return original_load(record, read_settings)

        @wraps(original_adopt)
        def adopt(store, workspace_id, paths, *, created=None):
            paths = list(paths)
            if len(paths) == 1 and self.contains(paths[0]):
                return [str(Path(paths[0]).absolute())]
            if any(self.contains(path) for path in paths):
                raise ValueError("Save temporary results using the generation gallery SAVE button.")
            return original_adopt(store, workspace_id, paths, created=created)

        WorkspaceStore.save = save_gallery
        WorkspaceStore.adopt = adopt
        workspaces.load_gallery = deepy_workspaces.load_gallery = load_gallery

        from shared.deepy import hybrid

        original_launch = hybrid.launch_gradio

        @wraps(original_launch)
        def launch(demo, service, args, **kwargs):
            allowed = kwargs.get("allowed_paths", [])
            # Gradio already serves its own upload/cache root. Strip galleries use output paths directly.
            kwargs["allowed_paths"] = [*allowed, str(self.outputs)]
            return original_launch(demo, service, args, **kwargs)

        hybrid.launch_gradio = launch

    def install_host_paths(self, host):
        for key, filename in {
            "AUTOSAVE_PATH": "queue.zip",
            "AUTOSAVE_TEMPLATE_PATH": "queue.zip",
            "AUTOSAVE_ERROR_FILENAME": "error_queue.zip",
        }.items():
            host[key] = str(self.directory / filename)

        for name in ("write_ram_debug_report", "write_vram_debug_report"):
            original = host[name]

            def write_debug(_directory, *args, _original=original, **kwargs):
                return _original(str(self.directory), *args, **kwargs)

            host[name] = write_debug

    def without_temporary_media(self, gallery):
        filtered = dict(gallery)
        for source in GALLERY_SOURCES:
            if source.files_key not in gallery:
                continue
            files = gallery[source.files_key]
            kept = [i for i, path in enumerate(files) if not self.contains(path)]
            filtered[source.files_key] = [files[i] for i in kept]
            if source.settings_key in gallery:
                settings = gallery[source.settings_key]
                filtered[source.settings_key] = [settings[i] for i in kept]
            if source.selected_key in gallery:
                previous = gallery[source.selected_key]
                filtered[source.selected_key] = (
                    -1 if previous < 0 or not kept else max(0, sum(i <= previous for i in kept) - 1)
                )
        return filtered

    def save_result(self, path, config, key, state):
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(self.outputs) or not path.is_file():
            raise ValueError("Select a result from this temporary session.")
        for member in workspace_storage.bundle_files(path).values():
            if not member.resolve().is_relative_to(self.outputs):
                raise ValueError("A result companion is outside the temporary output folder.")
        destination = Path(self.original_output_config(config, state=state)[key]).resolve()
        if destination.is_relative_to(self.directory.parent):
            raise ValueError("Choose an output folder outside the Temporator session directory.")
        saved, _ = workspace_storage.copy_bundle(path, destination)
        return saved


