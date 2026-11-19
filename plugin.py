"""Wan2GP Add-ons manager entry point."""

import atexit
from pathlib import Path

import gradio as gr

from shared.utils.gallery_sources import SOURCES
from shared.utils.plugins import WAN2GPPlugin

from .session import open_temporary_session
from .storage import MediaSession


class TemporatorPlugin(WAN2GPPlugin):
    def setup_ui(self):
        self.request_component("state")
        for name in ("get_gen_info", "gallery_choice", "server_config", "lock"):
            self.request_global(name)
        from shared.deepy import session_store

        directory = open_temporary_session(Path.cwd().resolve())
        self.session = MediaSession(directory)
        session_store.configure_sessions_root(directory / "deepy")
        self.session.install()
        self._host_paths_installed = False

    def post_ui_setup(self, components):
        if not self._host_paths_installed:
            host = self.get_gen_info.__globals__
            self.session.install_host_paths(host)
            # Wan2GP registers this handler before loading plugins. Its final
            # queue snapshot must run before the temporary session is removed.
            autosave = host["autosave_queue"]
            atexit.unregister(autosave)
            atexit.register(autosave)
            self._host_paths_installed = True
        self.insert_after("gallery_tabs", lambda: self.build_save(components["state"]))

    def candidate(self, state):
        gen = self.get_gen_info(state)
        with self.lock:
            if "in_progress" in gen:
                return None
            source = SOURCES.get(gen.get("current_gallery_source"))
            if source is None or source.id == "app":
                return None
            index = self.gallery_choice(gen, source)
            files = gen.get(source.files_key, ())
            if not 0 <= index < len(files):
                return None
            settings = gen.get(source.settings_key, ())
            metadata = settings[index] if index < len(settings) else None
            if isinstance(metadata, dict) and metadata.get("output_role") == "intermediate":
                return None
            path = Path(files[index]).resolve()
        return path if path.is_relative_to(self.session.outputs) and path.is_file() else None

    def build_save(self, state):
        with gr.Column() as panel:
            button = gr.Button("SAVE", visible=False)
            timer = gr.Timer(1)

            def refresh(state):
                return gr.update(visible=self.candidate(state) is not None)

            def save(state):
                from shared.utils.utils import get_media_kind

                path = self.candidate(state)
                if path is None:
                    raise gr.Error("Select an available result after generation completes.")
                key = {
                    "image": "image_save_path",
                    "audio": "audio_save_path",
                    "3d": "mesh_save_path",
                }.get(get_media_kind(str(path)), "save_path")
                try:
                    saved = self.session.save_result(path, self.server_config, key, state)
                except (OSError, ValueError) as exc:
                    raise gr.Error(f"SAVE failed: {exc}") from exc
                gr.Info(f"Saved to {saved}")

            timer.tick(refresh, inputs=[state], outputs=[button], queue=False, api_name=False, show_progress="hidden")
            button.click(save, inputs=[state], api_name=False, show_progress="minimal")
        return panel





