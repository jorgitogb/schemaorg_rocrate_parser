# Examples Directory

This directory contains JSON-LD files with Schema.org metadata for testing and batch processing.

## File Overview

### Single Dataset Examples (Small)
These files contain individual dataset examples for testing:

| File | Lines | Description |
|------|-------|-------------|
| `example_plabipd.json` | 55 | Single PLABIPD dataset |
| `example_edal.json` | 57 | Single e!DAL dataset |
| `example_openagrar.json` | 62 | Single OpenAgrar dataset |
| `example_bonares.json` | 74 | Single BonaRes dataset |
| `example_publisso.json` | 101 | Single PUBLISSO dataset |

### Full Dataset Collections (Large)
These files contain complete collections of multiple datasets:

| File | Datasets | Lines | Description |
|------|----------|-------|-------------|
| `edal_full.json` | 143 | 5,857 | Complete e!DAL dataset collection |
| `bonares_full.json` | 1,339 | 189,123 | Complete BonaRes dataset collection |

## Usage

### Process Small Examples (Recommended for Testing)

Process the small example files to test the workflow:

```bash
# Process only the small examples
python scripts/batch_processor.py examples/ --file example_bonares.json

# Or use a glob pattern to process all example_* files
for file in examples/example_*.json; do
    python scripts/batch_processor.py examples/ --file $(basename "$file")
done
```

### Process Full Collections (Production)

**Warning:** Processing full collections will create hundreds/thousands of ARCs and may take considerable time.

```bash
# Process edal_full.json (143 datasets)
python scripts/batch_processor.py examples/ --file edal_full.json

# Process bonares_full.json (1,339 datasets)
python scripts/batch_processor.py examples/ --file bonares_full.json
```

## Data Sources

- **BonaRes**: Soil research data from the BonaRes Data Centre
- **e!DAL**: Plant genomics and phenomics research data from IPK Gatersleben
- **OpenAgrar**: Agricultural research data repository
- **PLABIPD**: Plant Biosafety and IPR data
- **PUBLISSO**: Life sciences publication repository

## Structure

All files follow Schema.org JSON-LD format with `@type: "Dataset"`. The full collections are arrays of dataset objects:

```json
[
    {
        "@context": "http://schema.org",
        "@id": "10.5447/ipk/2012/1",
        "@type": "Dataset",
        "name": "Dataset title",
        "author": [...],
        ...
    },
    {
        "@id": "10.5447/ipk/2012/2",
        "@type": "Dataset",
        ...
    },
    ...
]
```

## Recommendations

1. **Start with small examples** to verify your workflow
2. **Test GitLab submission** with 1-2 examples before processing full collections
3. **Monitor GitLab quotas** when processing large collections
4. **Use filters** if you only need specific datasets from the full collections

## Creating Custom Subsets

To extract specific datasets from the full collections:

```python
import json

# Load full collection
with open('examples/edal_full.json', 'r') as f:
    datasets = json.load(f)

# Extract first 10 datasets
subset = datasets[:10]

# Save subset
with open('examples/edal_subset.json', 'w') as f:
    json.dump(subset, f, indent=2)
```

Or use command line tools:

```bash
# Extract first dataset from edal_full.json
python3 -c "import json; data=json.load(open('edal_full.json')); print(json.dumps([data[0]], indent=2))" > edal_single.json
```
