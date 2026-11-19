# TemporatorWan2GP

**Keep a generation only when you choose SAVE.**

[Русская версия](README.ru.md) · [MIT license](LICENSE) · [Development](docs/DEVELOPMENT.md) · [Changelog](CHANGELOG.md)

Temporator is a Windows add-on for the [WanGP (Wan2GP)](https://github.com/deepbeepmeep/WanGP) web interface. It keeps supported generation media in an isolated temporary session and adds **SAVE** below the **Media Generator** and **Edit** galleries. Start WanGP as usual.

## Install

Requires Windows and WanGP 19.292 or later. The add-on uses WanGP's bundled Python and Gradio.

1. Open **Apps & PlugIn Manager → Install from URL**.
2. Enter the repository URL and click **Download and Install from URL**.

   ```text
   https://github.com/Teutonick/TemporatorWan2GP
   ```

3. Enable **TemporatorWan2GP** and restart WanGP.

Already using a manually copied version? Back up or move its folder outside WanGP's `plugins` folder before installing from URL. WanGP needs a Git checkout to update an add-on.

## Generate, preview, save

1. Generate or edit media in the native interface.
2. Once the queue finishes, select a result in the gallery. Temporator keeps it available for preview and reuse during the session.
3. Click **SAVE** to copy it and its recognized companion files to your WanGP output folder. A workspace with dedicated storage uses its own output folder.

Repeated saves of the same bundle reuse the existing copy. Temporator removes its session when Python shuts down normally. Following a forced stop, it clears leftover sessions the next time the add-on loads. Existing files and explicitly exported results remain on disk.

## What the session covers

| Within Temporator's scope | Outside its scope |
| --- | --- |
| Native Media Generator and Edit outputs and processing files routed through WanGP's output resolver | Independent write paths used by tools such as Media Flow, Motion Designer, or third-party add-ons |
| Gradio uploads and previews, and standard temporary files created after activation | Browser caches, OS storage, remote services, and other processes |
| Automatic queue snapshots and the Deepy session directory for this run | Headless CLI and separate MCP/API processes; existing data and model caches |

Preview files are written to disk during the session. Cleanup is ordinary file removal. See [disclaimer and third-party terms](DISCLAIMER.md) and [security reporting](SECURITY.md).

## Update

Use **Update** in the add-on manager, then restart WanGP. For a manual installation, replace the add-on files from the same release while WanGP is closed. See the [maintainer release guide](docs/RELEASING.md) for details on how WanGP finds updates.
