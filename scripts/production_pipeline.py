#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production pipeline for processing Schema.org datasets to ARCs and uploading to GitLab.

This script:
1. Reads all JSON files from input_schemaorg/
2. Parses Schema.org metadata to ISA RO-Crate
3. Creates ARCs using ARCtrl
4. Uploads to GitLab (dev or production)

Usage:
    python scripts/production_pipeline.py --env .env.prod
    python scripts/production_pipeline.py --env .env.dev --dry-run
"""

import argparse
import sys
import io
from pathlib import Path

# Set UTF-8 encoding for stdout/stderr on Windows to handle Unicode characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemaorg_rocrate_parser.parser import SchemaOrgParser
from schemaorg_rocrate_parser.rocrate_builder import ISAROCrateBuilder


def process_dataset(input_file: Path, output_base: Path, dry_run: bool = False) -> list:
    """
    Process a single Schema.org JSON file to RO-Crates (one per dataset).
    
    Args:
        input_file: Path to input JSON file
        output_base: Base directory for output
        dry_run: If True, don't write files
        
    Returns:
        list of dicts with processing results for each dataset
    """
    results = []
    
    try:
        print(f"\n{'='*80}")
        print(f"Processing: {input_file.name}")
        print(f"{'='*80}")
        
        # Parse Schema.org metadata
        parser = SchemaOrgParser()
        metadata = parser.parse_file(input_file)
        
        # Check if there are multiple datasets
        datasets = metadata.get('datasets', [])
        if not datasets:
            result = {
                'file': input_file.name,
                'dataset_name': input_file.stem,
                'status': 'error',
                'message': 'No datasets found in file',
                'output_dir': None
            }
            results.append(result)
            print("✗ Error: No datasets found")
            return results
        
        print(f"Found {len(datasets)} dataset(s) in file")
        
        # Process each dataset separately
        for idx, dataset in enumerate(datasets, 0):
            dataset_id = dataset.get('identifier', dataset.get('@id', f'dataset_{idx}'))
            # Sanitize dataset name for directory
            dataset_name = str(dataset_id).replace('/', '_').replace(':', '_').replace('\\', '_')
            
            result = {
                'file': input_file.name,
                'dataset_name': dataset_name,
                'dataset_id': dataset_id,
                'status': 'pending',
                'message': '',
                'output_dir': None
            }
            
            try:
                print(f"\n  [{idx}/{len(datasets)}] Processing dataset: {dataset_id}")
                
                # Create single-dataset metadata
                single_dataset_metadata = {
                    'datasets': [dataset],
                    'persons': metadata.get('persons', []),
                    'organizations': metadata.get('organizations', []),
                    'publications': metadata.get('publications', [])
                }
                
                # Create output directory for this dataset
                output_dir = output_base / f"{input_file.stem}_{dataset_name}_arc"
                
                if not dry_run:
                    output_dir.mkdir(parents=True, exist_ok=True)
                
                # Build RO-Crate for this dataset
                builder = ISAROCrateBuilder()
                builder.build_from_parsed_data(single_dataset_metadata)
                
                if not dry_run:
                    builder.save(str(output_dir))
                    result['output_dir'] = output_dir
                
                result['status'] = 'success'
                result['message'] = f"Created RO-Crate at {output_dir}"
                print(f"  ✓ Success: {result['message']}")
                
            except Exception as e:
                result['status'] = 'error'
                result['message'] = str(e)
                print(f"  ✗ Error: {result['message']}")
            
            results.append(result)
        
    except Exception as e:
        # Top-level error affecting entire file
        result = {
            'file': input_file.name,
            'dataset_name': input_file.stem,
            'status': 'error',
            'message': str(e),
            'output_dir': None
        }
        results.append(result)
        print(f"✗ Error: {e}")
        
        # Save failed dataset
        if not dry_run:
            error_file = output_base / f"{input_file.stem}_error.json"
            import shutil
            shutil.copy(input_file, error_file)
            print(f"  Saved error file: {error_file}")
    
    return results


def create_arcs(output_base: Path, results: list, dry_run: bool = False) -> list:
    """
    Create ARCs from successful RO-Crates.
    
    Args:
        output_base: Base directory containing RO-Crates
        results: List of processing results
        dry_run: If True, don't create ARCs
        
    Returns:
        Updated results list
    """
    from scripts.arc_creator import ARCCreator
    
    for result in results:
        if result['status'] != 'success' or result['output_dir'] is None:
            continue
            
        try:
            print(f"\nCreating ARC for: {result['file']}")
            
            rocrate_file = result['output_dir'] / 'ro-crate-metadata.json'
            if not rocrate_file.exists():
                result['arc_status'] = 'error'
                result['arc_message'] = 'RO-Crate file not found'
                continue
            
            if not dry_run:
                creator = ARCCreator(rocrate_file)
                arc = creator.create_arc()
                creator.write_arc(arc)
            
            result['arc_status'] = 'success'
            result['arc_message'] = 'ARC created successfully'
            print("✓ ARC created")
            
        except Exception as e:
            result['arc_status'] = 'error'
            result['arc_message'] = str(e)
            print(f"✗ ARC creation failed: {e}")
    
    return results


def upload_to_gitlab(results: list, env_file: str, branch: str, dry_run: bool = False) -> list:
    """
    Upload successful ARCs to GitLab.
    
    Args:
        results: List of processing results
        env_file: Path to environment config file
        branch: Branch name for commits
        dry_run: If True, don't upload
        
    Returns:
        Updated results list
    """
    from scripts.gitlab_submitter import GitLabSubmitter
    import json
    
    if dry_run:
        print("\n[DRY RUN] Would upload ARCs to GitLab")
        return results
    
    submitter = GitLabSubmitter(config_path=env_file)
    
    for result in results:
        if result.get('arc_status') != 'success' or result['output_dir'] is None:
            continue
            
        try:
            # Find ARC directory (should be the only subdirectory with isa.investigation.xlsx file)
            arc_dirs = [d for d in result['output_dir'].iterdir() if d.is_dir() and (d / 'isa.investigation.xlsx').exists()]
            
            if not arc_dirs:
                result['gitlab_status'] = 'error'
                result['gitlab_message'] = 'No ARC directory found'
                continue
            
            arc_dir = arc_dirs[0]
            print(f"\nUploading ARC: {arc_dir.name}")
            
            # Extract topics from RO-Crate metadata
            topics = []
            base_name = None
            rocrate_file = result['output_dir'] / 'ro-crate-metadata.json'
            if rocrate_file.exists():
                with open(rocrate_file, 'r', encoding='utf-8') as f:
                    rocrate_data = json.load(f)
                    # Find the root entity (Investigation)
                    root_entity = next((e for e in rocrate_data.get('@graph', []) if e.get('@id') == './'), None)
                    if root_entity and 'keywords' in root_entity:
                        keywords = root_entity['keywords']
                        if isinstance(keywords, list):
                            topics = keywords
                        elif isinstance(keywords, str):
                            # Split comma-separated keywords
                            topics = [k.strip() for k in keywords.split(',') if k.strip()]
            
            # Find avatar based on input file name and get base name for default topics
            avatar_path = None
            if 'file' in result:
                # Get the base name without extension (e.g., "edal" from "edal_full.json")
                file_stem = Path(result['file']).stem
                # Remove any suffix like "_full"
                base_name = file_stem.split('_')[0]
                
                # Check for matching avatar in assets folder
                assets_dir = Path(__file__).parent.parent / 'assets'
                for ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    potential_avatar = assets_dir / f"{base_name}{ext}"
                    if potential_avatar.exists():
                        avatar_path = potential_avatar
                        break
            
            # If no keywords found, use default topics
            if not topics and base_name:
                topics = [base_name, "FAIRagro", "Dataset"]
            
            project = submitter.submit_arc(
                arc_directory=arc_dir,
                project_name=None,  # Will use Investigation Identifier
                branch=branch,
                topics=topics if topics else None,
                avatar_path=avatar_path
            )
            
            result['gitlab_status'] = 'success'
            result['gitlab_message'] = project['web_url']
            print(f"✓ Uploaded: {project['web_url']}")
            
        except Exception as e:
            result['gitlab_status'] = 'error'
            result['gitlab_message'] = str(e)
            print(f"✗ Upload failed: {e}")
    
    return results


def print_summary(results: list):
    """Print processing summary."""
    print(f"\n\n{'='*80}")
    print("PROCESSING SUMMARY")
    print(f"{'='*80}\n")
    
    total = len(results)
    ro_crate_success = sum(1 for r in results if r['status'] == 'success')
    arc_success = sum(1 for r in results if r.get('arc_status') == 'success')
    gitlab_success = sum(1 for r in results if r.get('gitlab_status') == 'success')
    
    print(f"Total datasets: {total}")
    print(f"RO-Crate created: {ro_crate_success}/{total}")
    print(f"ARCs created: {arc_success}/{total}")
    print(f"GitLab uploads: {gitlab_success}/{total}")
    
    print("\n--- Details ---\n")
    for r in results:
        status_icon = "✓" if r['status'] == 'success' else "✗"
        print(f"{status_icon} {r['file']} → {r['dataset_name']}")
        print(f"  Dataset ID: {r.get('dataset_id', 'N/A')}")
        print(f"  RO-Crate: {r['status']} - {r['message']}")
        if 'arc_status' in r:
            print(f"  ARC: {r['arc_status']} - {r['arc_message']}")
        if 'gitlab_status' in r:
            print(f"  GitLab: {r['gitlab_status']} - {r['gitlab_message']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Production pipeline for Schema.org to ARC conversion',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('input_schemaorg'),
        help='Input directory containing Schema.org JSON files (default: input_schemaorg)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('output_crates'),
        help='Output directory for RO-Crates and ARCs (default: output_crates)'
    )
    
    parser.add_argument(
        '--env',
        type=str,
        default='.env',
        help='Environment config file (default: .env)'
    )
    
    parser.add_argument(
        '--branch',
        type=str,
        default='main',
        help='GitLab branch name (default: main)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform dry run without creating files or uploading'
    )
    
    parser.add_argument(
        '--skip-gitlab',
        action='store_true',
        help='Skip GitLab upload step'
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    if not args.input.exists():
        print(f"Error: Input directory not found: {args.input}")
        return 1
    
    # Find all JSON files
    json_files = list(args.input.glob('*.json'))
    
    if not json_files:
        print(f"Error: No JSON files found in {args.input}")
        return 1
    
    print(f"Found {len(json_files)} JSON file(s) to process")
    if args.dry_run:
        print("\n[DRY RUN MODE - No files will be created or uploaded]\n")
    
    # Process all datasets to RO-Crates (each dataset becomes a separate result)
    results = []
    for json_file in sorted(json_files):
        file_results = process_dataset(json_file, args.output, args.dry_run)
        results.extend(file_results)
    
    # Create ARCs from successful RO-Crates
    results = create_arcs(args.output, results, args.dry_run)
    
    # Upload to GitLab
    if not args.skip_gitlab:
        results = upload_to_gitlab(results, args.env, args.branch, args.dry_run)
    
    # Print summary
    print_summary(results)
    
    # Return error code if any failures
    failed = sum(1 for r in results if r['status'] != 'success')
    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
