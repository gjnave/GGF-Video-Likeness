# Release locations

- Primary Codeberg: https://codeberg.org/Cognibuild/Headliner-Animate
- GitHub full-source mirror: https://github.com/gjnave/Headliner-Animate
- Private daysinging Drive project backup folder: https://drive.google.com/drive/folders/1kuC5NNpgYpSCmJyVE_jAfvKJz9LQeVoI
- Stable source archive Drive ID: `1G_h82Vp0eqnGwQdTj6vMXI6dd8QvT2IL`
- Private model backup folder: https://drive.google.com/drive/folders/1oKyE9u_SWB93Qsdhl44qTu7D21cblslZ

When making a Drive backup, update the existing backup bytes with the same file ID. Drive backups are not required for Git updates and must not be described as an automatic updater fallback. Model backups remain private and are not the customer download source.

Both Git repositories must contain the individual source files and the same main-branch commit. Publish with Git push; never substitute an uploaded source ZIP for the repository. The app checks Git revisions and installs fast-forward updates from Codeberg, falling back to GitHub. Drive is a backup only, not an automatic Git update source. Installer ZIPs are customer download packages, not the repository update mechanism. Public source contains no BAT installers, environments, weights, logs, local settings or personal media.

Model backup parts are 96 MiB each because the connector transfer path has a 100 MiB limit. `backup-manifest.json` records per-part and full-model SHA-256 hashes. Restore with `restore_model_backup.py BACKUP_FOLDER MODEL_DESTINATION` after downloading all parts. Neither originals nor older package snapshots should be deleted without explicit permission.
