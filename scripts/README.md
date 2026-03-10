# Scripts

This directory contains executable scripts for working with ARCs and GitLab.

## Production Pipeline (Recommended)

The `production_pipeline.py` script is the main production tool for processing Schema.org datasets. It automatically:

- Reads all JSON files from `input_schemaorg/`
- Converts to ISA RO-Crates
- Creates ARCs using ARCtrl
- Uploads to GitLab (dev or production)

### Production Usage

#### Dry run (test without creating files)

```bash
python scripts/production_pipeline.py --dry-run
```

#### Process and upload to development

```bash
python scripts/production_pipeline.py --env .env.dev
```

#### Process and upload to production

```bash
python scripts/production_pipeline.py --env .env.prod --branch main
```

#### Process only (skip GitLab upload)

```bash
python scripts/production_pipeline.py --skip-gitlab
```

## Batch Processor (Alternative)

The `batch_processor.py` script processes multiple JSON files containing Schema.org metadata, converting them to ISA RO-Crates, creating ARC structures, and optionally submitting them to GitLab.

### Usage

#### Process all JSON files in a directory

```bash
python scripts/batch_processor.py examples/
```

#### Specify custom output directory

```bash
python scripts/batch_processor.py examples/ --output my_output/
```

#### Process and submit to GitLab

```bash
python scripts/batch_processor.py examples/ --submit
```

#### Process a single file

```bash
python scripts/batch_processor.py examples/ --file example_bonares.json
```

### Workflow

For each JSON file, the batch processor performs these steps:

1. **Parse** - Parses Schema.org JSON-LD metadata using `SchemaOrgParser`
2. **Build RO-Crate** - Creates ISA RO-Crate structure using `ISAROCrateBuilder`
3. **Create ARC** - Generates ARC directory structure using ARCtrl via `ARCCreator`
4. **Submit to GitLab** - (Optional) Uploads ARC to GitLab repository using `GitLabSubmitter`

### Output Structure

```
output_crates/
├── bonares_arc/
│   ├── ro-crate-metadata.json
│   └── [ARC_Name]/
│       ├── isa.investigation.xlsx
│       ├── studies/
│       ├── assays/
│       ├── workflows/
│       └── runs/
├── edal_arc/
│   ├── ro-crate-metadata.json
│   └── [ARC_Name]/
...
```

### GitLab Configuration

To enable GitLab submission, create a `.env` file in the project root with:

```env
GITLAB_URL=https://your-gitlab-instance.com
GITLAB_PRIVATE_TOKEN=your_private_token
GITLAB_NAMESPACE_ID=your_namespace_id
```

### GitLab Topics (Tags)

When submitting to GitLab, projects are automatically tagged with topics:

1. **Keywords from metadata**: Extracted from the dataset's `keywords` field
2. **Source identifier**: Derived from the filename (e.g., `edal` from `edal_full.json`)
3. **fairagro**: Always added to all projects
4. **dataset**: Added as fallback if no keywords are found

**Example:**

- File: `edal_full.json`
- Keywords: `"Pollen Embryogenese, Hordeum vulgare, Mikrosporen, Proteinanalyse"`
- Topics: `edal`, `fairagro`, `hordeum-vulgare`, `mikrosporen`, `pollen-embryogenese`, `proteinanalyse`

## Individual Scripts

- **arc_creator.py**: Create ARC structures from RO-Crate metadata using ARCtrl
- **gitlab_submit.py**: CLI tool for submitting individual ARCs to GitLab
- **gitlab_submitter.py**: GitLab API client for ARC submission

### Create an ARC

```bash
uv run python scripts/arc_creator.py output_crates/example/ro-crate-metadata.json
```

### Submit to GitLab

```bash
uv run python scripts/gitlab_submit.py output_crates/example/arc --branch main
```
