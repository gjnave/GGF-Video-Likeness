# Floyd Headliner Animate

- This is a separate app. Do not modify Headliner or Spokesman to develop it.
- Never delete files or folders without the user's explicit permission.
- Use the existing GGF navy/gold styling, readable dark dropdowns and compact mobile header.
- The primary flow is video → capture frame → select person → likeness preview → animation. There is no approval checkbox.
- Keep clean image pixels separate from selection overlays. Changing selection/reference must invalidate the preview.
- Preserve existing repository addresses and installation folder names for updater compatibility; visible product branding is Floyd Headliner Animate.
- Use app-local Comfy inference modules in an owned worker. No ComfyUI server, frontend or external installation.
- Never run both model stages simultaneously. Preserve inputs and previous outputs on errors/cancellation.
- Five seconds is a suggested first test, not a total-duration limit. Preserve original audio.
- Public source excludes models, personal media, jobs, logs, network settings, local paths, environments, BAT installers and installer ZIPs.
- Publish individual source files to Codeberg Cognibuild/Headliner-Animate (primary) and GitHub gjnave/Headliner-Animate. Push the same commit to both. Drive Software/GGF-Video-Likeness is backup storage, not a Git update server.
- Keep the existing Drive source file ID: update its contents rather than uploading a replacement file with a new ID.
- Updates use Git fetch plus fast-forward, not a manually uploaded source ZIP. Never reintroduce the archive-only Codeberg repository. Keep VERSION synchronized and report failed mirrors explicitly.
- Installer/update scripts live in the parent directory, not the public source repository. Use CMD, not PowerShell.
- Back up source before updates. Never replace/delete models, jobs, local configuration, or the environment.
- Keep all upstream licenses and attribution. Do not portray Viggle or ComfyUI as original GGF research.
