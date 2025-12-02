# Schema.org to ISA RO-Crate Parser

Parse Schema.org JSON-LD metadata into ISA (Investigation/Study/Assay) RO-Crate structure and submit to GitLab as ARC repositories.

## Overview

This tool converts Schema.org metadata (in JSON-LD format) into RO-Crate following the ISA model, generates ARCs (Annotated Research Contexts) using ARCtrl, and can submit them to GitLab repositories. It handles various JSON-LD structures that can represent the same information and normalizes them into a consistent RO-Crate format.

## Features

- **Flexible JSON-LD parsing**: Handles different JSON-LD structures:
  - Single entities
  - Arrays of entities
  - Named graphs (`@graph`)
  - Various Schema.org types (Dataset, Person, Organization, ScholarlyArticle, etc.)

- **ISA RO-Crate generation**: Creates Research Object Crates following ISA patterns
  
- **Entity mapping**: Automatically maps Schema.org types to RO-Crate entities:
  - `Dataset` → Investigation/Study
  - `Person` → Person entities with affiliations
  - `Organization` → Organization entities
  - `ScholarlyArticle` → Publication references

## Installation

Install dependencies using `uv`:

```bash
uv sync
```

Or using pip:

```bash
pip install -e .
```

## Usage

### Batch Processing (Recommended)

Process multiple JSON files from a folder, generate RO-Crates and ARCs, and optionally submit to GitLab:

```bash
# Process all JSON files in examples/ folder
python scripts/batch_processor.py examples/

# Process and submit to GitLab
python scripts/batch_processor.py examples/ --submit

# Custom output directory
python scripts/batch_processor.py examples/ --output my_output/

# Process a single file
python scripts/batch_processor.py examples/ --file example_bonares.json
```

The batch processor will:
1. Parse each JSON file's Schema.org metadata
2. Build ISA RO-Crate structures
3. Create ARC directories using ARCtrl
4. Optionally submit each ARC to GitLab

See [scripts/README.md](scripts/README.md) for detailed documentation.

### Command Line (Single File)

Parse a JSON-LD file and create an RO-Crate:

```bash
python main.py examples/example_edal.json -o output-crate
```

Output JSON-LD to stdout:

```bash
python main.py examples/example_bonares.json --json
```

### Python API

```python
from schemaorg_rocrate_parser import SchemaOrgParser, ISAROCrateBuilder

# Parse Schema.org JSON-LD
parser = SchemaOrgParser()
parsed_data = parser.parse_file("metadata.jsonld")

# Build RO-Crate
builder = ISAROCrateBuilder()
crate = builder.build_from_parsed_data(parsed_data)

# Save to disk
builder.save("my-rocrate")

# Or get as JSON-LD
json_ld = builder.to_json()
```

## Input Format Examples

### Single Dataset

```json
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "My Research Dataset",
  "description": "A comprehensive study",
  "author": {
    "@type": "Person",
    "name": "Jane Doe",
    "email": "jane@example.com"
  }
}
```

### Graph Structure

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@id": "#dataset1",
      "@type": "Dataset",
      "name": "My Dataset",
      "author": {"@id": "#person1"}
    },
    {
      "@id": "#person1",
      "@type": "Person",
      "name": "Jane Doe"
    }
  ]
}
```

## ARC Generation

Generate an ARC from the RO-Crate:

```bash
python arc_creator.py output_crates/edal_arc/ro-crate-metadata.json
```

This creates:

- `arc/isa.investigation.xlsx` - Investigation Excel file
- `arc/studies/` - Study directories
- `arc/assays/` - Assay directories
- `arc/arc_structure.json` - ARC structure metadata

## GitLab Submission

### Setup Credentials

1. Create a `.env` file (never commit this!):

```bash
cp .env.example .env
```

1. Edit `.env` with your GitLab credentials:

```env
GITLAB_URL=https://your-gitlab-instance.com
GITLAB_PRIVATE_TOKEN=your-private-token
GITLAB_NAMESPACE_ID=55
GITLAB_GROUP_ID=55
```

### Submit ARC to GitLab

```bash
# Submit an ARC to GitLab
python gitlab_submit.py output_crates/edal_arc/arc --name my-arc-project

# Overwrite existing project
python gitlab_submit.py output_crates/edal_arc/arc --name my-arc-project --overwrite

# Add description
python gitlab_submit.py output_crates/edal_arc/arc \
  --name my-arc-project \
  --description "Rice genome dataset ARC"
```

### Python API for GitLab

```python
from gitlab_submitter import GitLabSubmitter
from pathlib import Path

# Initialize with credentials from .env
submitter = GitLabSubmitter()

# Submit ARC
project = submitter.submit_arc(
    arc_directory=Path("output_crates/edal_arc/arc"),
    project_name="my-arc-project",
    description="My research ARC",
    overwrite=True
)

print(f"ARC submitted: {project['web_url']}")
```

## Output

The parser generates an RO-Crate directory with:

- `ro-crate-metadata.json`: The RO-Crate metadata file
- Properly structured entities following ISA patterns

## Development

Project structure:

```text
schemaorg_rocrate_parser/
├── __init__.py           # Package exports
├── parser.py             # JSON-LD parser
└── rocrate_builder.py    # RO-Crate builder
```

## Requirements

- Python >= 3.13
- rocrate >= 0.10.0
- rdflib >= 7.0.0
- pyld >= 2.0.0

## License

[Add your license here]
