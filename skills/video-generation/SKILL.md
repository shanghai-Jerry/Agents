---
name: video-generation
description: Use this skill when the user requests to generate, create, or imagine videos or images. Supports Gemini (Veo) and Volcengine Ark (Seedance/Doubao) providers.
---

# Video & Image Generation Skill

## Overview

This skill generates high-quality videos and images using structured prompts and Python scripts. It supports multiple AI providers:

- **Gemini Veo 3.1** — Video generation (text-to-video, image-to-video)
- **Volcengine Ark (Seedance)** — Video generation (text-to-video, image-to-video)
- **Volcengine Ark (Doubao)** — Image generation (text-to-image)

### Provider Selection

Check environment variables to determine which provider is available:

| Env Variable | Provider | Capability |
|---|---|---|
| `GEMINI_API_KEY` | Gemini Veo 3.1 | Video generation |
| `ARK_API_KEY` | Volcengine Ark | Video + Image generation |

If `ARK_API_KEY` is set, prefer Volcengine Ark for both video and image generation. If only `GEMINI_API_KEY` is set, use Gemini for video generation.

## Core Capabilities

- Create structured prompts for AI video/image generation
- Support reference images as guidance or first/last frame of videos
- Generate videos through async task submission + polling + download
- Generate images through synchronous API calls

## Workflow

### Step 1: Understand Requirements

When a user requests video or image generation, identify:

- **Subject/content**: What should be in the video/image
- **Style preferences**: Art style, mood, color palette
- **Technical specs**: Aspect ratio, composition, lighting, duration (for video)
- **Reference images**: Any images to guide generation
- **Output preference**: Desired output format and location

### Step 2: Create Prompt

For **Gemini video generation**: Create a JSON prompt file with descriptive content (structure is flexible — the entire file content is used as the text prompt).

For **Volcengine video/image generation**: The prompt can be a plain text string or read from a text file. No JSON structure required, but detailed descriptions improve quality.

### Step 3: Generate Reference Image (Optional)

If the image-generation skill is available and reference images would improve quality, generate them first.

### Step 4: Execute Generation

Choose the appropriate script based on the provider and task type.

---

## Gemini Video Generation

**Script**: `skills/video-generation/scripts/generate_gemini.py`
**Requires**: `GEMINI_API_KEY` environment variable

```bash
python skills/video-generation/scripts/generate_gemini.py \
  --prompt-file /path/to/prompt.json \
  --reference-images /path/to/ref1.jpg /path/to/ref2.jpg \
  --output-file /path/to/output.mp4 \
  --aspect-ratio 16:9
```

Parameters:

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--prompt-file` | Yes | — | Absolute path to prompt file (entire content used as prompt) |
| `--reference-images` | No | — | Absolute paths to reference images (space-separated) |
| `--output-file` | Yes | — | Absolute path to save the generated video |
| `--aspect-ratio` | No | 16:9 | Aspect ratio of the generated video |

**Flow**: Submit async task → Poll status (3s interval) → Download video on completion.

> Do NOT read the Python script. Just call it with the appropriate parameters.

---

## Volcengine Video Generation

**Script**: `skills/video-generation/scripts/generate_volcengine_video.py`
**Requires**: `ARK_API_KEY` environment variable
**Model**: `doubao-seedance-1-5-pro-251215` (default)

### Text-to-Video

```bash
python skills/video-generation/scripts/generate_volcengine_video.py \
  --prompt "A cat playing piano in a jazz bar, cinematic lighting" \
  --output-file /path/to/output.mp4 \
  --duration 5 \
  --ratio 16:9
```

Or using a prompt file:

```bash
python skills/video-generation/scripts/generate_volcengine_video.py \
  --prompt-file /path/to/prompt.txt \
  --output-file /path/to/output.mp4
```

### Image-to-Video

```bash
python skills/video-generation/scripts/generate_volcengine_video.py \
  --prompt "Animate the scene with slow camera zoom" \
  --reference-images /path/to/reference.jpg \
  --output-file /path/to/output.mp4
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

**Script**: `skills/video-generation/scripts/generate_volcengine_image.py`
**Requires**: `ARK_API_KEY` environment variable
**Model**: `doubao-seedance-1-0-t2i-250415` (default)

```bash
python skills/video-generation/scripts/generate_volcengine_image.py \
  --prompt "A serene Japanese garden with cherry blossoms, watercolor style" \
  --output-file /path/to/output.png \
  --size 1024x1024 \
  --num 1
```

Parameters:

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--prompt` | Yes | — | Text prompt for image generation |
| `--output-file` | Yes | — | Absolute path to save the generated image |
| `--model` | No | doubao-seedance-1-0-t2i-250415 | Volcengine Ark model identifier |
| `--size` | No | 1024x1024 | Image size in WxH format |
| `--num` | No | 1 | Number of images to generate (1-4) |
| `--seed` | No | — | Optional seed for reproducibility |

**Flow**: Synchronous API call → Download image(s) from returned URL(s).

> Do NOT read the Python script. Just call it with the appropriate parameters.

---

## Video Generation Example

User request: "Generate a short video clip depicting the opening scene from The Chronicles of Narnia"

### Step 1: Research & Plan

Search for details about the opening scene of "The Chronicles of Narnia: The Lion, the Witch and the Wardrobe".

### Step 2: Create Prompt File

Create a detailed text prompt file (e.g. `/tmp/narnia-farewell-scene.txt`):

```
World War II evacuation scene at a crowded London train station. Steam and smoke fill the air as children are being sent to the countryside to escape the Blitz. Close-up two-shot of Mrs. Pevensie and young Lucy Pevensie on the platform. Mrs. Pevensie says "You must be brave for me, darling. I'll come for you... I promise." Lucy responds "I will be, mother. I promise." A train whistle blows as the train begins to depart. Strings swell emotionally in the background. Cinematic lighting, 1940s period detail, warm golden tones mixed with cool blues of the steam.
```

### Step 3: Generate Reference Image (Optional)

If the image-generation skill is available, generate a reference image first.

### Step 4: Execute Video Generation

Using Volcengine Ark (preferred if `ARK_API_KEY` is set):
```bash
python skills/video-generation/scripts/generate_volcengine_video.py \
  --prompt-file /tmp/narnia-farewell-scene.txt \
  --reference-images /tmp/narnia-farewell-scene-01.jpg \
  --output-file /tmp/narnia-farewell-scene-01.mp4 \
  --duration 5 \
  --ratio 16:9
```

Using Gemini Veo (if only `GEMINI_API_KEY` is set):
```bash
python skills/video-generation/scripts/generate_gemini.py \
  --prompt-file /tmp/narnia-farewell-scene.txt \
  --reference-images /tmp/narnia-farewell-scene-01.jpg \
  --output-file /tmp/narnia-farewell-scene-01.mp4 \
  --aspect-ratio 16:9
```

## Output Handling

After generation:

- Present generated videos/images to the user using the appropriate presentation tool
- Provide a brief description of the generation result
- Offer to iterate or adjust if improvements are needed

## Notes

- Always use English for prompts regardless of the user's language
- Detailed, descriptive prompts produce significantly better results
- Reference images enhance generation quality, especially for consistency
- Video generation is async and may take several minutes — inform the user about estimated wait time
- Volcengine Ark video URLs are temporary; videos are automatically downloaded to the specified output path
