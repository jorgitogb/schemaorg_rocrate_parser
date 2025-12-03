"""
Batch processor for Schema.org JSON files to GitLab ARC submission.

This script processes multiple JSON files from a folder:
1. Parse Schema.org JSON-LD files
2. Build ISA RO-Crate structures
3. Create ARCs using ARCtrl
4. Submit ARCs to GitLab

Usage:
    python scripts/batch_processor.py examples/ --output output_crates/ --submit
"""

import argparse
import json
import sys
import hashlib
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path to import schemaorg_rocrate_parser
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemaorg_rocrate_parser import SchemaOrgParser, ISAROCrateBuilder
from scripts.arc_creator import ARCCreator
from scripts.gitlab_submitter import GitLabSubmitter


class BatchProcessor:
    """Process multiple JSON files and submit to GitLab."""
    
    def __init__(self, input_dir: Path, output_dir: Path, submit_to_gitlab: bool = False):
        """
        Initialize batch processor.
        
        Args:
            input_dir: Directory containing JSON files
            output_dir: Directory for output RO-Crate and ARC structures
            submit_to_gitlab: Whether to submit to GitLab after processing
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.submit_to_gitlab = submit_to_gitlab
        self.gitlab_submitter = None
        self.assets_dir = Path(__file__).parent.parent / "assets"
        
        if submit_to_gitlab:
            try:
                self.gitlab_submitter = GitLabSubmitter()
                print("✓ GitLab submitter initialized")
            except ValueError as e:
                print(f"Warning: {e}")
                print("Continuing without GitLab submission...")
                self.submit_to_gitlab = False
    
    @staticmethod
    def generate_short_name(dataset_id: str, max_length: int = 50) -> str:
        """
        Generate a short, consistent, unique folder name from a dataset ID.
        
        Uses a combination of sanitized prefix and hash to ensure:
        - Same dataset always gets same name (deterministic)
        - No duplicates (hash uniqueness)
        - Reasonable length (truncated + hash)
        
        Args:
            dataset_id: Original dataset identifier
            max_length: Maximum length for the folder name
            
        Returns:
            Short folder name
        """
        # Sanitize the dataset_id: remove special characters, replace with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', dataset_id)
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Create a short hash of the original ID for uniqueness
        hash_obj = hashlib.sha256(dataset_id.encode('utf-8'))
        short_hash = hash_obj.hexdigest()[:8]  # Use first 8 chars of hash
        
        # Calculate how much space we have for the prefix
        # Format: prefix_hash (with underscore separator)
        hash_part_length = len(short_hash) + 1  # +1 for underscore
        max_prefix_length = max_length - hash_part_length
        
        if max_prefix_length < 1:
            # If max_length is too short, just use the hash
            return short_hash
        
        # Truncate the sanitized name if needed
        if len(sanitized) > max_prefix_length:
            prefix = sanitized[:max_prefix_length]
        else:
            prefix = sanitized
        
        # Combine prefix and hash
        return f"{prefix}_{short_hash}"
    
    @staticmethod
    def extract_source_from_filename(filename: str) -> str:
        """
        Extract source name from filename.
        
        Examples:
            edal_full.json -> edal
            example_bonares.json -> bonares
            plabipd.json -> plabipd
        
        Args:
            filename: JSON filename
            
        Returns:
            Source name
        """
        # Remove extension
        name = filename.replace('.json', '')
        
        # Remove common prefixes in order (most specific first)
        if name.startswith('test_first3_'):
            name = name.replace('test_first3_', '', 1)
        elif name.startswith('test_avatar_'):
            name = name.replace('test_avatar_', '', 1)
        elif name.startswith('example_'):
            name = name.replace('example_', '', 1)
        
        # Remove suffix
        name = name.replace('_full', '')
        
        # Take first part if underscore-separated
        parts = name.split('_')
        return parts[0].lower()
    
    @staticmethod
    def extract_topics(dataset_data: dict, source: str) -> list[str]:
        """
        Extract GitLab topics from dataset metadata.
        
        Topics are derived from:
        1. Dataset keywords (if available)
        2. Source name (from filename)
        3. Default topic 'fairagro'
        4. Fallback 'dataset' if no keywords
        
        Args:
            dataset_data: Dataset JSON-LD data
            source: Source name (e.g., 'edal', 'bonares')
            
        Returns:
            List of topics (GitLab tags)
        """
        topics = set()
        
        # Always add fairagro
        topics.add('fairagro')
        
        # Always add source
        topics.add(source)
        
        # Extract keywords from dataset
        keywords = dataset_data.get('keywords', '')
        
        if keywords:
            # Keywords can be a string or array
            if isinstance(keywords, str):
                # Split by common delimiters
                keyword_list = re.split(r'[,;]', keywords)
                for kw in keyword_list:
                    kw = kw.strip()
                    if kw:
                        # Sanitize keyword for GitLab (lowercase, no spaces)
                        sanitized_kw = re.sub(r'[^\w-]', '-', kw.lower())
                        sanitized_kw = re.sub(r'-+', '-', sanitized_kw).strip('-')
                        if sanitized_kw and len(sanitized_kw) > 2:  # Skip very short tags
                            topics.add(sanitized_kw)
            elif isinstance(keywords, list):
                for kw in keywords:
                    if isinstance(kw, str):
                        kw = kw.strip()
                        if kw:
                            sanitized_kw = re.sub(r'[^\w-]', '-', kw.lower())
                            sanitized_kw = re.sub(r'-+', '-', sanitized_kw).strip('-')
                            if sanitized_kw and len(sanitized_kw) > 2:
                                topics.add(sanitized_kw)
        
        # If no keywords were found, add 'dataset' as fallback
        if len(topics) == 2:  # Only fairagro and source
            topics.add('dataset')
        
        return sorted(list(topics))  # Sort for consistency
    
    def find_avatar(self, source: str) -> Optional[Path]:
        """
        Find avatar/logo file for a given source.
        
        Looks for image files matching the source name in the assets directory.
        
        Args:
            source: Source name (e.g., 'edal', 'bonares')
            
        Returns:
            Path to avatar file if found, None otherwise
        """
        # Check for common image extensions
        for ext in ['.png', '.jpg', '.jpeg', '.svg']:
            avatar_path = self.assets_dir / f"{source}{ext}"
            if avatar_path.exists():
                return avatar_path
        return None
    
    def find_json_files(self) -> List[Path]:
        """
        Find all JSON files in input directory.
        
        Returns:
            List of JSON file paths
        """
        json_files = list(self.input_dir.glob("*.json"))
        if not json_files:
            print(f"No JSON files found in {self.input_dir}")
            return []
        
        print(f"\nFound {len(json_files)} JSON file(s):")
        for f in json_files:
            print(f"  - {f.name}")
        return json_files
    
    def process_dataset(self, dataset_data: dict, dataset_id: str, json_file: Path) -> Dict[str, Any]:
        """
        Process a single dataset through the entire pipeline.
        
        Args:
            dataset_data: Dataset JSON-LD data
            dataset_id: Identifier for this dataset (e.g., file name or DOI)
            json_file: Original JSON file path (for reference)
        
        Returns:
            Dictionary with processing results
        """
        result = {
            'dataset_id': dataset_id,
            'success': False,
            'rocrate_path': None,
            'arc_path': None,
            'gitlab_url': None,
            'error': None
        }
        
        print(f"\n{'='*80}")
        print(f"Processing dataset: {dataset_id}")
        print(f"{'='*80}")
        
        # Extract source and topics early for GitLab submission
        source = self.extract_source_from_filename(json_file.name)
        topics = self.extract_topics(dataset_data, source)
        avatar_path = self.find_avatar(source)
        
        result['topics'] = topics
        if avatar_path:
            result['avatar'] = str(avatar_path)
        
        try:
            # Step 1: Parse Schema.org JSON-LD
            print("\n[1/4] Parsing Schema.org metadata...")
            parser = SchemaOrgParser()
            
            # Create a temporary file-like object for the parser
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                json.dump(dataset_data, tmp, indent=2)
                tmp_path = Path(tmp.name)
            
            try:
                parsed_data = parser.parse_file(tmp_path)
            finally:
                tmp_path.unlink()  # Clean up temp file
            
            print("  ✓ Parsed successfully")
            
            # Step 2: Build ISA RO-Crate
            print("\n[2/4] Building ISA RO-Crate...")
            builder = ISAROCrateBuilder()
            crate = builder.build_from_parsed_data(parsed_data)
            
            # Generate short, unique folder name
            short_name = self.generate_short_name(dataset_id, max_length=50)
            output_path = self.output_dir / short_name
            output_path.mkdir(parents=True, exist_ok=True)
            
            print(f"  → Folder: {short_name}")
            
            # Save RO-Crate
            builder.save(str(output_path))
            rocrate_metadata_path = output_path / "ro-crate-metadata.json"
            result['rocrate_path'] = str(rocrate_metadata_path)
            result['short_name'] = short_name
            print(f"  ✓ RO-Crate saved to: {output_path}")
            
            # Step 3: Create ARC structure
            print("\n[3/4] Creating ARC structure...")
            arc_creator = ARCCreator(rocrate_metadata_path)
            arc = arc_creator.create_arc()
            
            # Use the ARC's identifier if available, otherwise use our short name
            # Always sanitize to remove forbidden characters (umlauts, special chars)
            arc_name = arc.Identifier if arc.Identifier else short_name
            arc_name = self.generate_short_name(arc_name, max_length=50)
            
            arc_path = output_path / arc_name
            
            # Write ARC to filesystem using ARCtrl
            arc.Write(str(arc_path))
            result['arc_path'] = str(arc_path)
            result['arc_name'] = arc_name
            print(f"  ✓ ARC created at: {arc_path}")
            
            # Step 4: Submit to GitLab (if enabled)
            if self.submit_to_gitlab and self.gitlab_submitter:
                print("\n[4/4] Submitting to GitLab...")
                try:
                    description = f"ARC generated from {dataset_id} (source: {source})"
                    
                    project = self.gitlab_submitter.submit_arc(
                        arc_directory=arc_path,
                        project_name=arc_name,
                        description=description,
                        overwrite=True,  # Overwrite if exists
                        topics=topics,  # Add topics
                        avatar_path=avatar_path  # Add avatar if found
                    )
                    result['gitlab_url'] = project['web_url']
                    print(f"  ✓ Submitted to GitLab: {project['web_url']}")
                except Exception as e:
                    print(f"  ✗ GitLab submission failed: {e}")
                    result['error'] = f"GitLab submission: {str(e)}"
            else:
                print("\n[4/4] Skipping GitLab submission (not enabled)")
                print(f"  Topics would be: {', '.join(topics)}")
                if avatar_path:
                    print(f"  Avatar would be: {avatar_path}")
            
            result['success'] = True
            print(f"\n✓ Successfully processed {dataset_id}")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"\n✗ Error processing {dataset_id}: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def process_file(self, json_file: Path) -> List[Dict[str, Any]]:
        """
        Process a JSON file that may contain a single dataset or array of datasets.
        
        Args:
            json_file: Path to JSON file
        
        Returns:
            List of processing results (one per dataset)
        """
        print(f"\n{'='*80}")
        print(f"Loading: {json_file.name}")
        print(f"{'='*80}")
        
        try:
            # Load JSON data
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Determine if it's a single dataset or array
            if isinstance(data, list):
                print(f"  → Found {len(data)} datasets in array")
                datasets = data
                # Generate IDs for each dataset
                dataset_ids = []
                for i, ds in enumerate(datasets):
                    ds_id = ds.get('@id', f"{json_file.stem}_{i+1}")
                    dataset_ids.append(ds_id)
            else:
                print(f"  → Found single dataset")
                datasets = [data]
                # Use file name or dataset @id
                ds_id = data.get('@id', json_file.stem.replace('example_', ''))
                dataset_ids = [ds_id]
            
            # Process each dataset
            results = []
            for i, (dataset, dataset_id) in enumerate(zip(datasets, dataset_ids), 1):
                if len(datasets) > 1:
                    print(f"\n[Dataset {i}/{len(datasets)}]")
                result = self.process_dataset(dataset, dataset_id, json_file)
                result['source_file'] = json_file.name
                results.append(result)
            
            return results
            
        except json.JSONDecodeError as e:
            error_result = {
                'source_file': json_file.name,
                'dataset_id': json_file.stem,
                'success': False,
                'error': f"JSON decode error: {str(e)}"
            }
            print(f"\n✗ Error: Invalid JSON in {json_file.name}: {e}")
            return [error_result]
        except Exception as e:
            error_result = {
                'source_file': json_file.name,
                'dataset_id': json_file.stem,
                'success': False,
                'error': str(e)
            }
            print(f"\n✗ Error loading {json_file.name}: {e}")
            import traceback
            traceback.print_exc()
            return [error_result]
    
    def process_all(self) -> List[Dict[str, Any]]:
        """
        Process all JSON files in input directory.
        
        Returns:
            Flattened list of processing results for each dataset
        """
        json_files = self.find_json_files()
        if not json_files:
            return []
        
        all_results = []
        for json_file in json_files:
            file_results = self.process_file(json_file)  # Returns list
            all_results.extend(file_results)  # Flatten the list
        
        return all_results
    
    def print_summary(self, results: List[Dict[str, Any]]) -> None:
        """
        Print summary of processing results.
        
        Args:
            results: List of processing results
        """
        print(f"\n\n{'='*80}")
        print("PROCESSING SUMMARY")
        print(f"{'='*80}\n")
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"Total datasets: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}\n")
        
        if successful:
            print("✓ Successfully processed:")
            for r in successful:
                dataset_label = r.get('dataset_id', r.get('source_file', 'unknown'))
                print(f"  • {dataset_label}")
                if r.get('source_file'):
                    print(f"    Source: {r['source_file']}")
                if r.get('topics'):
                    print(f"    Topics: {', '.join(r['topics'])}")
                if r.get('gitlab_url'):
                    print(f"    GitLab: {r['gitlab_url']}")
                elif r.get('arc_path'):
                    print(f"    ARC: {r['arc_path']}")
        
        if failed:
            print("\n✗ Failed to process:")
            for r in failed:
                dataset_label = r.get('dataset_id', r.get('source_file', 'unknown'))
                print(f"  • {dataset_label}")
                if r.get('source_file'):
                    print(f"    Source: {r['source_file']}")
                print(f"    Error: {r.get('error', 'Unknown error')}")
        
        print(f"\n{'='*80}\n")


def main():
    """Main entry point for batch processor."""
    parser = argparse.ArgumentParser(
        description="Batch process Schema.org JSON files to ARCs and optionally submit to GitLab"
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Directory containing JSON files to process"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output_crates",
        help="Output directory for RO-Crates and ARCs (default: output_crates)"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit ARCs to GitLab after creation"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process only a specific file (by name)"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input directory '{args.input_dir}' not found or not a directory")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("BATCH PROCESSOR - Schema.org to ARC to GitLab")
    print("="*80)
    print(f"\nInput directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"GitLab submission: {'Enabled' if args.submit else 'Disabled'}")
    
    # Initialize processor
    processor = BatchProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        submit_to_gitlab=args.submit
    )
    
    # Process files
    if args.file:
        # Process single file (returns list of results)
        json_file = input_dir / args.file
        if not json_file.exists():
            print(f"Error: File '{args.file}' not found in {input_dir}")
            sys.exit(1)
        results = processor.process_file(json_file)  # Already returns a list
    else:
        # Process all files
        results = processor.process_all()
    
    # Print summary
    if results:
        processor.print_summary(results)
    
    # Exit with error code if any failures
    failed = [r for r in results if not r.get('success', False)]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
