---
name: video-generation
description: Use this skill when the user requests to generate, create, or imagine videos or images. Supports Volcengine Ark (Seedance/Doubao) providers.
---

# Video & Image Generation Skill

## Overview

This skill generates high-quality videos and images using structured prompts and Python scripts. It supports:

- **Volcengine Ark (Seedance)** — Video generation (text-to-video, image-to-video)
- **Volcengine Ark (Doubao Seedream)** — Image generation (text-to-image)

**Requires**: `ARK_API_KEY` environment variable

## Environment Paths

| Item | Path |
|---|---|
| Scripts | `/mnt/skills/public/video-generation/scripts/` |
| Workspace (prompts) | `/mnt/user-data/workspace/` |
| Output files | `/mnt/user-data/outputs/` |

> You don't need to check the folder under `/mnt/user-data`.

## Core Capabilities

- Create structured prompts for AI video/image generation
- Generate reference images to guide video generation (optional but recommended)
- Generate videos through async task submission + polling + download
- Generate images through synchronous API calls

## Workflow

### Step 1: Understand Requirements

When a user requests video generation, identify:

- Subject/content: What should be in the image
- Style preferences: Art style, mood, color palette
- Technical specs: Aspect ratio, composition, lighting
- Reference image: Any image to guide generation
- You don't need to check the folder under `/mnt/user-data`

### Step 2: Create Structured Prompt

Generate a structured JSON file in `/mnt/user-data/workspace/` with naming pattern: `{descriptive-name}.json`

### Step 3: Generate Reference Image (Optional, Recommended for Video)

If reference images would improve video quality, generate them first using the image generation script:

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_image.py \
  --prompt "A detailed description of the desired scene..." \
  --output-file /mnt/user-data/outputs/reference.jpg \
  --size 2K
```

- If only 1 image is provided, it will be used as the guided frame of the video
- Reference images significantly enhance generation quality and visual consistency

### Step 4: Execute Generation

Choose the appropriate script based on the task type.

---

## Volcengine Video Generation

**Script**: `/mnt/skills/public/video-generation/scripts/generate_volcengine_video.py`
**Requires**: `ARK_API_KEY` environment variable
**Model**: `doubao-seedance-1-5-pro-251215` (default)

### Text-to-Video

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_video.py \
  --prompt "A cat playing piano in a jazz bar, cinematic lighting" \
  --output-file /mnt/user-data/outputs/output.mp4 \
  --duration 5 \
  --ratio 16:9
```

Or using a prompt file:

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_video.py \
  --prompt-file /mnt/user-data/workspace/prompt.txt \
  --output-file /mnt/user-data/outputs/output.mp4
```

### Image-to-Video

Use the reference image generated in Step 3:

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_video.py \
  --prompt "Animate the scene with slow camera zoom" \
  --reference-images /mnt/user-data/outputs/reference.jpg \
  --output-file /mnt/user-data/outputs/output.mp4 \
  --duration 5 \
  --ratio 16:9
```

Reference images can be local file paths or HTTP URLs.

Parameters:

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--prompt` | No* | — | Text prompt (use `--prompt-file` instead for file-based prompts) |
| `--prompt-file` | No* | — | Path to a text file containing the prompt |
| `--reference-images` | No | — | Paths to reference images or HTTP URLs (space-separated) |
| `--output-file` | Yes | — | Absolute path to save the generated video (.mp4) |
| `--model` | No | doubao-seedance-1-5-pro-251215 | Volcengine Ark model identifier |
| `--duration` | No | 5 | Video duration in seconds (5 or 10) |
| `--ratio` | No | 16:9 | Aspect ratio (16:9, 9:16, or 1:1) |
| `--generate-audio` | No | false | Generate audio for the video |

*One of `--prompt` or `--prompt-file` is required.

**Flow**: Submit async task → Poll status (5s interval) → Download video on completion.

> Do NOT read the Python script. Just call it with the appropriate parameters.

---

## Volcengine Image Generation

**Script**: `/mnt/skills/public/video-generation/scripts/generate_volcengine_image.py`
**Requires**: `ARK_API_KEY` environment variable
**Model**: `doubao-seedream-4-5-251128` (default)

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_image.py \
  --prompt "A serene Japanese garden with cherry blossoms, watercolor style" \
  --output-file /mnt/user-data/outputs/output.png \ 
  --size 2K
```

Parameters:

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--prompt` | Yes | — | Text prompt for image generation |
| `--output-file` | Yes | — | Absolute path to save the generated image |
| `--model` | No | doubao-seedream-4-5-251128 | Volcengine Ark model identifier |
| `--size` | No | 2K | Image size (2K, 4K, or WxH format like 1024x1024) |
| `--num` | No | 1 | Number of images to generate (1-4) |
| `--seed` | No | — | Optional seed for reproducibility |

**Flow**: Synchronous API call → Download image(s) from returned URL(s).

> Do NOT read the Python script. Just call it with the appropriate parameters.

---

## Video Generation Example

User request: "Generate a short video clip depicting the opening scene from The Chronicles of Narnia"

### Step 1: Research & Plan

Search for details about the opening scene of "The Chronicles of Narnia: The Lion, the Witch and the Wardrobe".

### Step 2: Create Prompt

Write a detailed text prompt:

```
World War II evacuation scene at a crowded London train station. Steam and smoke fill the air as children are being sent to the countryside to escape the Blitz. Close-up two-shot of Mrs. Pevensie and young Lucy Pevensie on the platform. Mrs. Pevensie says "You must be brave for me, darling. I'll come for you... I promise." Lucy responds "I will be, mother. I promise." A train whistle blows as the train begins to depart. Strings swell emotionally in the background. Cinematic lighting, 1940s period detail, warm golden tones mixed with cool blues of the steam.
```

### Step 3: Generate Reference Image (Optional)

Generate a reference image first for better video quality:

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_image.py \
  --prompt "World War II London train station, Mrs. Pevensie and young Lucy saying goodbye, steam and crowd, cinematic 1940s period detail, warm golden lighting, close-up two-shot" \
  --output-file /mnt/user-data/outputs/reference.jpg \
  --size 2K
```

### Step 4: Execute Video Generation

Using the reference image from Step 3:

```bash
python /mnt/skills/public/video-generation/scripts/generate_volcengine_video.py \
  --prompt "World War II evacuation scene at a crowded London train station. Steam and smoke fill the air as children are being sent to the countryside to escape the Blitz. Close-up two-shot of Mrs. Pevensie and young Lucy Pevensie on the platform." \
  --reference-images /mnt/user-data/outputs/reference.jpg \
  --output-file /mnt/user-data/outputs/output.mp4 \
  --duration 5 \
  --ratio 16:9
```

## Output Handling

After generation:

- Videos are typically saved in `/mnt/user-data/outputs/`
- Present the generated video to the user first using the appropriate presentation tool
- If a reference image was generated (Step 3), present it after the video
- Provide a brief description of the generation result
- Offer to iterate or adjust if improvements are needed

## Notes

- Always use English for prompts regardless of the user's language
- Detailed, descriptive prompts produce significantly better results
- Reference images enhance generation quality, especially for visual consistency
- Video generation is async and may take several minutes — inform the user about estimated wait time
- Volcengine Ark video/image URLs are temporary; files are automatically downloaded to the specified output path
