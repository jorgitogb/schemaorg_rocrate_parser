"""Create ARC structures from ISA RO-Crate using ARCtrl Python bindings."""

import argparse
import json
import re
from pathlib import Path
from arctrl import ARC


class ARCCreator:
    """Create ARC structures from RO-Crate metadata using ARCtrl."""
    
    def __init__(self, rocrate_path: Path):
        """Initialize ARC creator.
        
        Args:
            rocrate_path: Path to ro-crate-metadata.json file
        """
        self.rocrate_path = rocrate_path
        self.output_dir = rocrate_path.parent
        self.arc_identifier = None
    
    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """
        Sanitize identifier to only contain allowed characters.
        
        ARCtrl allows: letters, digits, underscore (_), dash (-), and whitespace ( ).
        German umlauts are transliterated to their standard replacements.
        
        Args:
            identifier: Original identifier
            
        Returns:
            Sanitized identifier
        """
        # Replace German umlauts with standard transliterations
        umlaut_map = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
            'ß': 'ss'
        }
        sanitized = identifier
        for umlaut, replacement in umlaut_map.items():
            sanitized = sanitized.replace(umlaut, replacement)
        
        # Replace any remaining special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_\- ]', '_', sanitized)
        # Remove consecutive underscores/spaces
        sanitized = re.sub(r'[_\s]+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized
        
    def create_arc(self) -> ARC:
        """Create ARC from RO-Crate metadata using ARCtrl.
        
        Returns:
            ARC object
        """
        # Load RO-Crate JSON
        with open(self.rocrate_path, 'r', encoding='utf-8') as f:
            rocrate_json_string = f.read()
            rocrate_data = json.loads(rocrate_json_string)
        
        # Create ARC from RO-Crate JSON using ARCtrl
        arc = ARC.from_rocrate_json_string(rocrate_json_string)
        
        # ARCtrl's from_rocrate_json_string doesn't automatically map date fields
        # So we need to manually set them from the RO-Crate metadata
        investigation_entity = next(
            (e for e in rocrate_data.get('@graph', []) if e.get('@id') == './'),
            None
        )
        
        if investigation_entity:
            # Set dates if they exist in the RO-Crate
            if 'submissionDate' in investigation_entity:
                arc.SubmissionDate = investigation_entity['submissionDate']
            if 'publicReleaseDate' in investigation_entity:
                arc.PublicReleaseDate = investigation_entity['publicReleaseDate']
                
            # Change identifier to title with sanitization
            title = investigation_entity.get('name', '')
            if title:
                # Sanitize to remove forbidden characters (umlauts, special chars)
                new_identifier = self.sanitize_identifier(title)
                arc.Identifier = new_identifier
                # Store identifier for ARC directory naming
                self.arc_identifier = new_identifier
            
            # Add DOI as comment
            original_identifier = investigation_entity.get('identifier', '')
            if original_identifier:
                from arctrl import Comment
                doi_comment = Comment('DOI', original_identifier)
                arc.Comments.append(doi_comment)
            
            # Handle Organization creators (ARCtrl only maps Person, not Organization)
            # Convert Organizations to Person contacts
            self._add_organization_contacts(arc, investigation_entity, rocrate_data)
        
        return arc
    
    def _add_organization_contacts(self, arc: ARC, investigation_entity: dict, rocrate_data: dict):
        """Add Organization entities as Person contacts to Investigation.
        
        Args:
            arc: ARC object
            investigation_entity: Investigation entity from RO-Crate
            rocrate_data: Complete RO-Crate data
        """
        from arctrl import Person
        
        # Get all graph entities for lookup
        entities_by_id = {e.get('@id'): e for e in rocrate_data.get('@graph', [])}
        
        # Check creators for Organizations
        creators = investigation_entity.get('creator', [])
        if not isinstance(creators, list):
            creators = [creators]
        
        for creator_ref in creators:
            if isinstance(creator_ref, dict):
                creator_id = creator_ref.get('@id', '')
                creator_entity = entities_by_id.get(creator_id, {})
                
                # If it's an Organization, create a Person contact from it
                if creator_entity.get('@type') == 'Organization':
                    org_name = creator_entity.get('name', '')
                    
                    # Parse contactPoint for person name and email
                    # Format: "FirstName LastName (email@domain.com)"
                    contact_point = creator_entity.get('contactPoint', '')
                    first_name = ''
                    last_name = ''
                    email = creator_entity.get('email', '')
                    
                    if isinstance(contact_point, str) and contact_point:
                        # Extract name and email from contactPoint
                        import re
                        match = re.match(r'^(.+?)\s*\(([^)]+)\)$', contact_point)
                        if match:
                            full_name = match.group(1).strip()
                            email = match.group(2).strip()
                            
                            # Split full name into first and last
                            name_parts = full_name.split()
                            if len(name_parts) > 1:
                                first_name = ' '.join(name_parts[:-1])
                                last_name = name_parts[-1]
                            elif len(name_parts) == 1:
                                last_name = name_parts[0]
                    
                    # Use organization name as last name if no contact person found
                    if not last_name:
                        last_name = org_name
                    
                    # Create a Person with the organization as affiliation
                    person = Person(
                        last_name=last_name,
                        first_name=first_name,
                        mid_initials='',
                        email=email,
                        phone='',
                        fax='',
                        address=creator_entity.get('address', ''),
                        affiliation=org_name
                    )
                    
                    # Add to Investigation contacts if not already present
                    if person not in arc.Contacts:
                        arc.Contacts.append(person)

    
    def write_arc(self, arc: ARC, arc_name: str | None = None):
        """Write ARC to disk.
        
        Args:
            arc: ARC object to write
            arc_name: Name for the ARC directory (default: use identifier)
        """
        if arc_name is None:
            # Use identifier if available, otherwise use parent directory name
            arc_name = self.arc_identifier or self.output_dir.name
        
        # Define ARC output path using identifier as directory name
        arc_path = self.output_dir / arc_name
        
        # Write ARC using ARCtrl
        arc.Write(str(arc_path))
        
        print(f"\n✓ ARC written to: {arc_path}")
        print(f"  - Investigation: {arc_path / 'isa.investigation.xlsx'}")
        
        # List created studies and assays
        studies_dir = arc_path / 'studies'
        if studies_dir.exists():
            study_count = len(list(studies_dir.iterdir()))
            print(f"  - Studies: {study_count}")
        
        assays_dir = arc_path / 'assays'
        if assays_dir.exists():
            assay_count = len(list(assays_dir.iterdir()))
            print(f"  - Assays: {assay_count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Create ARC from ISA RO-Crate metadata using ARCtrl'
    )
    parser.add_argument(
        'rocrate_path',
        type=str,
        help='Path to ro-crate-metadata.json file'
    )
    parser.add_argument(
        '-n', '--name',
        type=str,
        default=None,
        help='Name for the ARC (default: use parent directory name)'
    )
    
    args = parser.parse_args()
    
    # Create ARC
    print(f"Creating ARC from: {args.rocrate_path}")
    creator = ARCCreator(Path(args.rocrate_path))
    arc = creator.create_arc()
    creator.write_arc(arc, args.name)
    
    print("\nARC creation complete!")


if __name__ == '__main__':
    main()
