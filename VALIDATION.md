# Preview validation — 2026-10-05

Environment: Windows, RTX 4090 24 GB, Python 3.11, PyTorch 2.10.0+cu130, Gradio 6.29.0. A new app-owned environment was created; no existing app environment was modified.

## Completed inference checks

- Viggle short test: 22 frames, 384 × 672, 34.63 seconds including loading and saving. Result decoded correctly and visibly replaced the source character.
- Viggle windowed test: six seconds, 144 output frames, 384 × 672, 56-frame windows, three anchored windows, 98.29 seconds including loading, conditioning, sampling, final decode and original-audio mux. Output video and audio both have six-second duration. Internal grid padding is trimmed from the saved result.
- Headliner preview test: six steps, 768 working resolution, selected-head crop/composite, 18.08 seconds, 16.89 GiB peak PyTorch allocated VRAM. Exact outside-selection pixels and original frame dimensions were preserved.
- A 480p/124-frame-window trial slowed severely before its first sampling update and was stopped. This is why the fast default uses 384p and 56-frame windows. The larger settings remain user-selectable.

## UI and non-GPU checks

- Browser video upload populated the captured frame after one upload.
- Entered-time capture works in one click. Native paused-frame capture is wired to the video player's current time.
- Create and Settings activate the correct panels.
- At a 390-pixel phone viewport there was no horizontal overflow; visible access-dropdown text was light on a dark background. Screenshot capture was unavailable in this browser session, so layout evidence is the browser's rendered DOM and computed styles, not a saved visual screenshot.
- New environment builds the Gradio interface; pip reports no broken dependencies.
- Unit tests cover aspect/grid sizing, protected update paths, archive hashes, selection invalidation, exact mask boundaries, and cancellation of an owned child Python process.

## Not established by these checks

These examples do not prove identity tracking across crowded scenes, cuts, exits/re-entry, or arbitrary long videos. Multi-window output can drift. Smaller-GPU performance is not verified. Windows processing keeps the whole selected range in system RAM, so custom duration is not a promise of unlimited-length processing. Model-license clearance and public Drive source-fallback access are separate release requirements.
