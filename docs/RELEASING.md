# Release and update guide

WanGP's **Install from URL** clones the GitHub repository into `plugins/TemporatorWan2GP`. Keep the repository name and root-level `plugin.py`, `__init__.py`, and `plugin_info.json` stable. The manifest declares an extension and the minimum compatible WanGP version. The repository does not require a separate dependency installation.

## How WanGP updates

- The manager can read `plugin_info.json` from GitHub's default branch through `raw/HEAD`. Catalog comparisons prioritize the release date when present and use the version to break a tie. Use ISO dates and increase the version for every release.
- **Update** fetches `origin` and pulls the corresponding remote branch of the active local checkout. Keep the public default branch installable. A tag or GitHub Release alone will not update existing installations. ZIP copies and detached checkouts require manual maintenance.
- A listing in WanGP's upstream community catalog is optional for installation by URL. Request it separately upstream and use this repository's manifest as the source of its metadata.

[WanGP plug-in guide](https://github.com/deepbeepmeep/WanGP/blob/main/docs/PLUGINS.md) · [Manager implementation](https://github.com/deepbeepmeep/WanGP/blob/main/shared/utils/plugins.py) · [Community catalog](https://github.com/deepbeepmeep/WanGP/blob/main/plugins.json)

## Release checklist

1. Run the Windows tests and the manual host checks in [Development](DEVELOPMENT.md). Record the actual WanGP versions tested.
2. Update `version` and `date` in the manifest and add a matching changelog entry. Change `wan2gp_version` if the minimum host contract changes.
3. Publish the reviewed changes to the default branch. Optionally tag that same revision as `vX.Y.Z` and create a GitHub Release for pinned downloads and release notes.
4. In a clean Windows installation, test **Install from URL**, enable, and restart. In a second installation on the previous version, use **Update** and restart. Confirm the version and that **SAVE** appears for an eligible result.
5. If a release breaks updates or storage behavior, ship the fix with a higher version. Keep any older tags for manual recovery.

For manual rollback, close WanGP and use the files from a single known-good tag. Keep a backup of local modifications before replacing an installation.
