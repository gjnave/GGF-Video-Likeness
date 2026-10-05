# Release locations

- Primary Codeberg: https://codeberg.org/Cognibuild/GGF-Video-Likeness
- GitHub full-source mirror: https://github.com/gjnave/GGF-Video-Likeness
- Private daysinging Drive project backup folder: https://drive.google.com/drive/folders/1kuC5NNpgYpSCmJyVE_jAfvKJz9LQeVoI
- Stable source archive Drive ID: `1G_h82Vp0eqnGwQdTj6vMXI6dd8QvT2IL`
- Private model backup folder: https://drive.google.com/drive/folders/1oKyE9u_SWB93Qsdhl44qTu7D21cblslZ

Update the existing Drive source archive bytes with the same file ID. Do not replace it with a newly uploaded file. Public-read sharing must be enabled and anonymously tested before describing Drive as an operational customer fallback. Model backups remain private and are not the customer download source.

Codeberg accepts the source archive, README, VERSION, and updater at its root when CLI authentication is unavailable. GitHub stores the full source tree. `release-manifest.json` lists the exact payload hashes and is shared by both archive shapes. Source archives contain no BAT files, environments, weights, logs, local settings or personal media.

Model backup parts are 96 MiB each because the connector transfer path has a 100 MiB limit. `backup-manifest.json` records per-part and full-model SHA-256 hashes. Restore with `restore_model_backup.py BACKUP_FOLDER MODEL_DESTINATION` after downloading all parts. Neither originals nor older package snapshots should be deleted without explicit permission.
