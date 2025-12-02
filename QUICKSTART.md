# Quick Start Guide

This guide will help you process JSON files containing Schema.org metadata and submit them to GitLab as ARC repositories.

## Prerequisites

1. **Python 3.13+** installed
2. **GitLab account** with access to create projects (for submission)
3. **Git** installed (optional, for version control)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd schemaorg_rocrate_parser
```

2. Install dependencies:
```bash
uv sync
# or
pip install -e .
```

## Configuration (for GitLab submission)

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your GitLab credentials:
```env
GITLAB_URL=https://your-gitlab-instance.com
GITLAB_PRIVATE_TOKEN=your-private-token
GITLAB_NAMESPACE_ID=your-namespace-id
```

**How to get these values:**
- **GITLAB_URL**: Your GitLab instance URL (e.g., `https://gitlab.com`)
- **GITLAB_PRIVATE_TOKEN**: GitLab → User Settings → Access Tokens → Create a new token with `api` scope
- **GITLAB_NAMESPACE_ID**: GitLab → Your Group/User → Settings → General (find the Group ID or User ID)

## Basic Usage

### Process all examples (local only, no GitLab)

```bash
python scripts/batch_processor.py examples/
```

This will:
- Parse all JSON files in `examples/` folder
- Create RO-Crate structures in `output_crates/`
- Generate ARC directories for each

### Process and submit to GitLab

```bash
python scripts/batch_processor.py examples/ --submit
```

This will do everything above PLUS submit each ARC to GitLab as a new project.

### Process a single file

```bash
python scripts/batch_processor.py examples/ --file example_bonares.json
```

### Custom output directory

```bash
python scripts/batch_processor.py examples/ --output my_custom_output/
```

## Understanding the Output

After processing, you'll see output like:

```
output_crates/
├── bonares_arc/
│   ├── ro-crate-metadata.json          # RO-Crate metadata
│   └── [Project_Title]/                 # ARC directory (named after project)
│       ├── isa.investigation.xlsx      # ISA Investigation file
│       ├── studies/                    # Studies directory
│       ├── assays/                     # Assays directory
│       ├── workflows/                  # Workflows directory
│       └── runs/                       # Runs directory
├── edal_arc/
│   └── ...
└── ...
```

Each `*_arc/` folder contains:
1. **ro-crate-metadata.json**: The RO-Crate metadata file
2. **ARC directory**: Complete ARC structure ready for GitLab

## What the Batch Processor Does

For each JSON file in your input folder:

1. **Parse** Schema.org JSON-LD metadata
2. **Build** ISA RO-Crate structure
3. **Create** ARC directory with proper ISA structure
4. **Submit** (optional) to GitLab as a new project

## Troubleshooting

### "Missing required GitLab configuration"

Make sure you've created a `.env` file with valid credentials. See [Configuration](#configuration-for-gitlab-submission) above.

### "Project already exists in GitLab"

The batch processor uses `overwrite=True` by default, which will delete and recreate existing projects. If you want to keep existing projects, you'll need to modify the code or use a different project name.

### Import errors

Make sure you've installed all dependencies:
```bash
uv sync
```

Or if using pip:
```bash
pip install -e .
pip install arctrl python-dotenv requests
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [scripts/README.md](scripts/README.md) for script-specific documentation
- Explore the [examples/](examples/) folder for sample input files

## Example Workflow

```bash
# 1. Add your JSON files to the examples folder
cp my_metadata.json examples/

# 2. Process all files locally (test first)
python scripts/batch_processor.py examples/

# 3. Review the generated ARCs in output_crates/

# 4. Submit to GitLab when ready
python scripts/batch_processor.py examples/ --submit

# 5. Check your GitLab for the new ARC projects!
```

## Support

For issues or questions, please open an issue on the project repository.
