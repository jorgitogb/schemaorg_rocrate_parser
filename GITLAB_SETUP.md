# GitLab Submission with Topics and Avatars

This guide explains how to submit ARCs to GitLab with automatic topic tagging and logo/avatar assignment.

## Features

When submitting ARCs to GitLab, the batch processor automatically:

1. **Extracts topics** from dataset keywords
2. **Adds source-based topics** (edal, bonares, etc.)
3. **Sets project avatar/logo** from the assets folder
4. **Tags with 'fairagro'** for all projects

## Setup

### 1. Configure GitLab Credentials

Create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
```env
GITLAB_URL=https://your-gitlab-instance.com
GITLAB_PRIVATE_TOKEN=your_private_token
GITLAB_NAMESPACE_ID=your_namespace_id
```

**How to get these values:**

- **GITLAB_URL**: Your GitLab instance URL (e.g., `https://gitlab.com` or `https://datahub-dev.ipk-gatersleben.de`)
- **GITLAB_PRIVATE_TOKEN**: 
  - Go to GitLab → User Settings → Access Tokens
  - Create a token with `api` scope
- **GITLAB_NAMESPACE_ID**: 
  - Go to your Group/User settings
  - Find the Group ID or User ID in the URL or settings

### 2. Prepare Logos (Optional)

Place logo files in the `assets/` directory with the source name:

```
assets/
├── bonares.png
├── edal.png
├── openagrar.png
├── publisso.png
└── thunen_atlas.png
```

**Naming convention:**
- File name must match the source extracted from JSON filename
- Supported formats: `.png`, `.jpg`, `.jpeg`, `.svg`
- Example: `edal_full.json` → looks for `assets/edal.png`

## Topics Generation

Topics are automatically generated from:

### 1. Source Name
Extracted from filename:
- `edal_full.json` → `edal`
- `example_bonares.json` → `bonares`
- `plabipd.json` → `plabipd`

### 2. Keywords from Dataset
Extracted from the `keywords` field in the JSON metadata:
```json
{
  "@type": "Dataset",
  "keywords": "Pollen Embryogenese, Hordeum vulgare, Mikrosporen, Proteinanalyse"
}
```

Keywords are:
- Converted to lowercase
- Special characters replaced with hyphens
- Split by commas/semicolons
- Filtered (minimum 3 characters)

### 3. Default Topics
- `fairagro` - Added to all projects
- `dataset` - Added only if no keywords found

## Example Topics

| File | Keywords | Topics |
|------|----------|--------|
| `edal_full.json` | `"Pollen Embryogenese, Hordeum vulgare"` | `edal`, `fairagro`, `hordeum-vulgare`, `pollen-embryogenese` |
| `bonares.json` | `""` (empty) | `bonares`, `dataset`, `fairagro` |
| `example_plabipd.json` | `["plant", "biosafety"]` | `biosafety`, `fairagro`, `plabipd`, `plant` |

## Usage

### Dry Run (No GitLab Submission)

Test topic and avatar detection without submitting:

```bash
uv run scripts/batch_processor.py examples/ --file example_edal.json
```

Output shows:
```
[4/4] Skipping GitLab submission (not enabled)
  Topics would be: edal, fairagro, hordeum-vulgare, mikrosporen, pollen-embryogenese, proteinanalyse
  Avatar would be: /path/to/assets/edal.png
```

### Submit to GitLab

Submit with topics and avatar:

```bash
uv run scripts/batch_processor.py examples/ --file example_edal.json --submit
```

### Using the Test Script

A helper script is provided for testing:

```bash
./test_gitlab_submission.sh
```

This script:
- Checks for `.env` file
- Shows available logos
- Prompts before submitting
- Submits `example_edal.json` to GitLab

## What Gets Created in GitLab

When a project is submitted, GitLab will have:

### Project Information
- **Name**: ARC identifier (e.g., `Physiologische_und_bioanalytische_Untersu_18ffd233`)
- **Description**: `ARC generated from {dataset_id} (source: {source})`
- **Visibility**: Private
- **Namespace**: Your configured namespace

### Topics/Tags
Visible in project overview, allows filtering:
- Source identifier (e.g., `edal`)
- `fairagro` (always present)
- Keywords from metadata
- `dataset` (if no keywords)

### Avatar/Logo
- Set from `assets/{source}.png`
- Displayed in project list and project page
- Helps visually identify data source

### Repository Contents
Complete ARC structure:
```
isa.investigation.xlsx
studies/
assays/
workflows/
runs/
```

## Troubleshooting

### Avatar Not Uploading

If the avatar doesn't appear:
1. Check file exists: `ls assets/{source}.png`
2. Verify file format (PNG, JPG, SVG)
3. Check file size (GitLab has limits, usually 200KB)
4. Look for warnings in output

### Topics Not Appearing

Topics are case-sensitive and must be valid:
- No spaces (converted to hyphens)
- Minimum 3 characters
- Alphanumeric and hyphens only

### GitLab API Errors

Common issues:
- **401 Unauthorized**: Check `GITLAB_PRIVATE_TOKEN`
- **403 Forbidden**: Token needs `api` scope
- **404 Not Found**: Check `GITLAB_NAMESPACE_ID`
- **Project exists**: Use `--overwrite` or set `overwrite=True`

## Batch Processing

Process multiple files:

```bash
# All examples (5 small files)
uv run scripts/batch_processor.py examples/ --submit

# Full collection (143 datasets)
uv run scripts/batch_processor.py examples/ --file edal_full.json --submit
```

Each dataset gets:
- Unique short folder name (max 50 chars)
- Topics from its keywords
- Same source logo for all from that source

## Example Complete Workflow

```bash
# 1. Setup
cp .env.example .env
# Edit .env with your credentials

# 2. Check available sources and logos
ls examples/*.json
ls assets/*.png

# 3. Test without submission
uv run scripts/batch_processor.py examples/ --file example_edal.json

# 4. Submit one example
uv run scripts/batch_processor.py examples/ --file example_edal.json --submit

# 5. Check GitLab
# Verify project has topics and avatar

# 6. Process all examples
uv run scripts/batch_processor.py examples/ --submit
```

## API Details

The implementation uses:

- **GitLab Projects API**: Creates projects with topics
- **GitLab Upload API**: Sets project avatar via multipart form upload
- **GitLab Commits API**: Uploads all ARC files in single commit

Topics are added during project creation via the `topics` parameter.
Avatar is uploaded after project creation via PUT request with file upload.
