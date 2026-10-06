# Floyd Headliner Animate

**A new look. The same performance.** A purpose-built Get Going Fast app in the Floyd Headliner family.

## Get going fast

Visit **[GetGoingFast.pro](https://getgoingfast.pro)** for GGF tools and setup helpers.
Watch **[The AI Hobby Guy on YouTube](https://youtube.com/@TheAIHobbyGuy)** for practical local-AI demonstrations.

Upload a video, capture a clear frame, select the person's head, and upload a replacement photo. The app uses Headliner's likeness-transfer engine behind the scenes. Review that frame, then animate it through your chosen video range. No exporting between apps and no ComfyUI installation or server.

## Simple workflow

1. Upload a video. Play/pause and **Capture paused frame**, or enter an exact capture time.
2. Click the center of the whole head. Adjust the gold box to include all hair, ears and the visible back of the head, leaving space for a new hairstyle. Upload a clear replacement photo.
3. **Make likeness preview** and review it.
4. Choose a start time and duration, then **Animate preview**.

An already edited, full-size frame from Headliner or another editor can also be imported.
Original audio is retained. Results are saved inside `jobs/<job-id>/`; each MP4 has a timestamp and unique suffix so downloads have different names. The taller output player has download and fullscreen controls. A persistent generation banner shows elapsed time and progress; the previous displayed video clears when a new generation starts, while saved files remain.

Use the frame timeline or Previous/Next frame buttons to choose another reference moment. Entered-time capture and capturing the paused player are also available.

Output shape defaults to the uploaded video's displayed orientation, including phone rotation metadata. The detected input and planned output dimensions are shown. Choose Portrait, Landscape or Square to override it; other shapes add padding instead of cropping or stretching the subject. The short-edge setting controls resolution independently of orientation.

Your workspace is automatically saved on this computer and restored when the same browser reopens the same app address. It includes uploaded media, the selected frame, controls, approval and completed results. Keep browser site storage enabled. A new temporary public URL has separate browser storage, so it does not automatically identify your previous workspace. The saved files remain in `jobs/workspaces/`.

## Duration and quality

The default is a five-second fast 384p-short-edge trial, not a hard duration limit. Enter another duration or `0` for the rest of the video. Long clips use overlapping, five-frame-anchored windows. Default window length is 56 frames at 24 fps; the upstream full window of 124 frames is available under More control. Custom windows round to the H3 `17n + 5` grid.

On the development RTX 4090, a six-second 384 × 672 example completed in 98.3 seconds including loading, three sampling windows, decoding and original-audio muxing. A 480p/124-frame-window trial was stopped after severe slowdown. These are specific test cases, not a speed or quality guarantee for every video.

Start with one clear person in a continuous shot. Multiple people, occlusions, scene cuts, abrupt motion and subject re-entry can cause identity drift or changes to bystanders. Selection isolates the image-editing step; it is not a guaranteed person-tracking system for video. Always review the final result.

The whole selected range is currently decoded into system RAM and the final output is decoded together. Windowing reduces sampling VRAM pressure but does not make unlimited-duration processing memory-free. Reduce resolution, duration or window length if memory runs out. Previous results are preserved.

## Models and hardware

**Model-license restriction:** the current MiniMax H3 terms exclude the U.S., EU, U.K. and South Korea absent separate permission. Viggle Animate inherits those terms. This technical preview is not cleared for unrestricted distribution; review [RELEASE-NOTICE.md](RELEASE-NOTICE.md) before use or deployment.

Windows 64-bit, Python 3.11, an NVIDIA GPU and a recent CUDA-13-compatible NVIDIA driver. The development GPU is an RTX 4090 (24 GB). Lower-VRAM compatibility is not guaranteed.

Model downloads: about **24.2 GiB video weights** plus **17.7 GiB image weights**. An existing Headliner model installation can be reused read-only via `local_settings.json`. Otherwise the installer downloads them. Allow additional space for Python, dependencies, working video and outputs.

- [Viggle Animate converted/pruned INT8, DMD speed adapter and frozen conditioning](https://huggingface.co/drbaph/Viggle-Animate-ComfyUI)
- [MiniMax H3 INT8 video VAE](https://huggingface.co/Kijai/MiniMax-H3-experimental)
- [Qwen Image 2.1 model and VAE](https://huggingface.co/Comfy-Org/Qwen-Image-2.1)
- [Qwen3 VL encoder](https://huggingface.co/Comfy-Org/Qwen3-VL)
- [BFS likeness adapter](https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap)
- [Qwen Viggle Turbo speed adapter](https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo)

Exact revisions, sizes and SHA-256 hashes are in `model_manifest.json`. The image Turbo adapter is different from the Viggle Animate video model.

## Manual source setup

Create a Python 3.11 environment, install `torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0` from `https://download.pytorch.org/whl/cu130`, then install `requirements.txt`. Run `python download_models.py`, then `python app.py`.

The local server starts at port 7862, automatically trying another port if occupied. Phone access is optional under Settings. Local access remains login-free even when the separate remote endpoint uses a password. Blank remote password explicitly disables login; anyone with the link can use the app. Public Gradio links are temporary.

Updates preserve private files and model downloads. Source order: **Codeberg first → GitHub → Google Drive**. Keep a release's source archive and VERSION synchronized across all three. The Drive source backup must be set to public read access before it can serve as an anonymous installer fallback; private backup storage alone is not a working public mirror.

## Attribution and responsible use

This app reuses Floyd Headliner's Qwen integration and selected ComfyUI inference modules. Video conditioning and windowed sampling are adapted from the Apache-2.0 [Viggle Animate node project](https://github.com/bhardwajRahul/ComfyUI-Viggle-Animate-H3), commit `6ae081af5b3175f99ef7cddebd5dfaf93390ab70`.

`vendor/comfy_core/LICENSE` contains ComfyUI's GPLv3 terms; `vendor/viggle/LICENSE` contains the Apache license; `vendor/viggle/MODEL-LICENSE` contains MiniMax H3 model terms. Third-party software and models retain their own licenses. No model weights or personal media are included in this repository.

`LICENSE-HEADLINER` preserves the original Headliner license for its reused image-worker code; it does not replace any upstream license.

Use only media and likenesses you have the right and consent to edit. Do not use for deceptive impersonation or nonconsensual content. Identify outputs as AI-generated. Experimental preview build: evaluate your own inputs and hardware before production work.
