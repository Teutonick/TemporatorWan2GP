# Development

## Code map

| File | Responsibility |
| --- | --- |
| `plugin_info.json` | WanGP manager discovery, compatibility and release metadata |
| `plugin.py` | Plug-in lifecycle, gallery selection and SAVE events |
| `session.py` | Windows session ownership, temp configuration and cleanup |
| `storage.py` | Output routing, transient workspace galleries and explicit bundle export |

WanGP calls `setup_ui` before building Gradio components. Preserve that order so the upload folder and component caches resolve to the same session. During `post_ui_setup`, the add-on patches the host's queue paths and registers SAVE in each gallery UI. Temporary workspace paths remain available in the live gallery and are filtered from persistent manifests. Export uses the original WanGP destination resolver and bundle copier.

The host internals used by this add-on include `WorkspaceStore.save/adopt`, `workspace_storage.output_config`, `hybrid.launch_gradio`, and the gallery component names. On a WanGP upgrade, check their signatures, when they are called, and whether any new code imports their symbols directly. Keep old user output directories and shared system temp outside cleanup.

## Run the tests

From the repository root in PowerShell with Python 3.11 or later:

```powershell
python -m unittest discover -s tests -v
```

Windows tests exercise real session directories and lock contention. The gallery tests use small host doubles so CI runs without WanGP, Gradio, model weights or a GPU. Tests that exercise temporary paths confine them to their own fixture directories. CI tests Python 3.11 and 3.12 on Windows.

## Host smoke test for each supported release

1. Install from URL, enable and start normally. Check the selected version in the manager.
2. With isolated test output folders, generate a small result in **Media Generator** and use it in **Edit**. Check upload handling and preview. Verify the configured output folders are empty before **SAVE**.
3. Save an image, a video with companions, and an audio or 3D result when available. Check configured type-specific paths and repeat in a dedicated workspace. Verify duplicate clicks and existing destination filenames.
4. Use a workspace switch to verify unsaved items remain available in-process while persistent workspace data omits their paths.
5. Exit normally and verify the session is gone and exports are intact. Force-stop a second run with unsaved media, restart normally and verify that stale session is gone.
6. Disable the add-on and restart. Verify native output behavior returns.

Use synthetic inputs. Record any modality, host build, or update path you could not exercise.

## Compatibility work

Prefer upstream storage and lifecycle hooks when available. For a new write path, identify its owner, confirm which files are created, and add a focused regression test before extending the supported scope.
