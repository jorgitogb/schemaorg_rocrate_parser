"""Build ISA RO-Crate from parsed Schema.org metadata."""

from typing import Any, Dict, Optional
from rocrate.rocrate import ROCrate


class ISAROCrateBuilder:
    """Build ISA-compliant RO-Crate from Schema.org metadata."""
    
    def __init__(self, crate_id: Optional[str] = None):
        """Initialize RO-Crate builder.
        
        Args:
            crate_id: Identifier for the RO-Crate
        """
        self.crate = ROCrate()
        self.crate_id = crate_id or "./"
        self.added_entities = {}  # Track added entities by @id
        self.studies = []  # Track studies
        self.assays = []  # Track assays
        
    def build_from_parsed_data(self, parsed_data: Dict[str, Any]) -> ROCrate:
        """Build RO-Crate from parsed Schema.org data.
        
        Args:
            parsed_data: Parsed metadata from SchemaOrgParser
            
        Returns:
            Populated RO-Crate object
        """
        # First add all Persons and Organizations
        if parsed_data.get('persons'):
            for person in parsed_data['persons']:
                self._add_person(person)
        
        if parsed_data.get('organizations'):
            for org in parsed_data['organizations']:
                self._add_organization(org)
        
        # Add Publications
        if parsed_data.get('publications'):
            for pub in parsed_data['publications']:
                self._add_publication(pub)
        
        # Build Investigation from Dataset(s)
        if parsed_data.get('datasets'):
            for dataset in parsed_data['datasets']:
                self._add_investigation(dataset)
        
        return self.crate
    
    def _add_investigation(self, dataset: Dict[str, Any]):
        """Add Investigation entity to RO-Crate root dataset.
        
        Args:
            dataset: Dataset metadata from Schema.org
        """
        # Extract name and description
        name = self._extract_first_value(dataset.get('name', ''))
        description = self._extract_first_value(dataset.get('description', ''))
        
        # Truncate name to avoid Windows path length issues (max 260 chars)
        # Leave room for path prefix and file extensions (~100 chars for safety)
        if len(name) > 100:
            name = name[:97] + '...'
        
        props: Dict[str, Any] = {
            'additionalType': 'Investigation',
            'name': name,
            'description': description,
        }
        
        # Add identifier - generate one if missing or empty
        identifier = dataset.get('identifier', dataset.get('@id', ''))
        if identifier:
            identifier = self._extract_first_value(identifier)
        
        # If identifier is empty or None, generate one from name or use uuid
        if not identifier:
            import hashlib
            name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
            identifier = f"dataset_{name_hash}"
        
        props['identifier'] = identifier
        
        # Add dates
        if dataset.get('datePublished'):
            date_published = self._extract_first_value(dataset['datePublished'])
            props['datePublished'] = date_published
            # Add ISA-specific date fields
            props['publicReleaseDate'] = date_published
            # Use datePublished as fallback for submissionDate if dateCreated not available
            if not dataset.get('dateCreated'):
                props['submissionDate'] = date_published
        
        if dataset.get('dateCreated'):
            date_created = self._extract_first_value(dataset['dateCreated'])
            props['dateCreated'] = date_created
            # Add ISA submission date
            props['submissionDate'] = date_created
        
        if dataset.get('dateModified'):
            props['dateModified'] = self._extract_first_value(dataset['dateModified'])
        
        # Add license - ensure it has @id if it's an object
        if dataset.get('license'):
            license_val = dataset['license']
            if isinstance(license_val, list):
                license_val = license_val[0] if license_val else ''
            
            # If license is a dict (CreativeWork) without @id, add one
            if isinstance(license_val, dict) and '@id' not in license_val:
                license_name = license_val.get('name', 'license')
                license_val['@id'] = f"#license_{hash(license_name) & 0x7FFFFFFF}"
            
            props['license'] = license_val
        
        # Add keywords
        if dataset.get('keywords'):
            keywords = dataset['keywords']
            if isinstance(keywords, str):
                props['keywords'] = keywords.split(', ')
            elif isinstance(keywords, list):
                # Handle both string keywords and DefinedTerm objects
                keyword_list = []
                for kw in keywords:
                    if isinstance(kw, dict) and kw.get('@type') == 'DefinedTerm':
                        # Add DefinedTerm entity and keep reference
                        defined_term_ref = self._add_defined_term(kw)
                        keyword_list.append(defined_term_ref)
                    elif isinstance(kw, str):
                        keyword_list.append(kw)
                    else:
                        keyword_list.append(kw)
                props['keywords'] = keyword_list
            else:
                props['keywords'] = keywords
        
        # Add language
        if dataset.get('inLanguage'):
            in_lang = dataset['inLanguage']
            if isinstance(in_lang, list):
                # Handle Language objects or simple strings
                lang_list = []
                for lang in in_lang:
                    if isinstance(lang, dict) and lang.get('@type') == 'Language':
                        lang_list.append(lang)
                    elif isinstance(lang, str):
                        lang_list.append(lang)
                    else:
                        lang_list.append(lang)
                props['inLanguage'] = lang_list
            else:
                props['inLanguage'] = in_lang
        
        # Handle creators/authors - convert to references
        creators = []
        
        # Process author field
        if dataset.get('author'):
            authors = dataset['author']
            if not isinstance(authors, list):
                authors = [authors]
            for author in authors:
                creator_ref = self._process_creator(author)
                if creator_ref:
                    creators.append(creator_ref)
        
        # Process creator field
        if dataset.get('creator'):
            creator_list = dataset['creator']
            if not isinstance(creator_list, list):
                creator_list = [creator_list]
            for creator in creator_list:
                creator_ref = self._process_creator(creator)
                if creator_ref and creator_ref not in creators:
                    creators.append(creator_ref)
        
        if creators:
            props['creator'] = creators
        
        # Handle publisher
        if dataset.get('publisher'):
            publisher = dataset['publisher']
            publisher_ref = self._process_creator(publisher)
            if publisher_ref:
                props['publisher'] = publisher_ref
        
        # Handle contributor
        if dataset.get('contributor'):
            contributors = dataset['contributor']
            if not isinstance(contributors, list):
                contributors = [contributors]
            contrib_refs = []
            for contrib in contributors:
                contrib_ref = self._process_creator(contrib)
                if contrib_ref:
                    contrib_refs.append(contrib_ref)
            if contrib_refs:
                props['contributor'] = contrib_refs
        
        # Handle sourceOrganization
        if dataset.get('sourceOrganization'):
            source_orgs = dataset['sourceOrganization']
            if not isinstance(source_orgs, list):
                source_orgs = [source_orgs]
            org_refs = []
            for org in source_orgs:
                org_ref = self._process_creator(org)
                if org_ref:
                    org_refs.append(org_ref)
            if org_refs:
                props['sourceOrganization'] = org_refs
        
        # Handle funder
        if dataset.get('funder'):
            funders = dataset['funder']
            if not isinstance(funders, list):
                funders = [funders]
            funder_refs = []
            for funder in funders:
                funder_ref = self._process_creator(funder)
                if funder_ref:
                    funder_refs.append(funder_ref)
            if funder_refs:
                props['funder'] = funder_refs
        
        # Handle funding - skip for now as Grant objects need special handling
        # if dataset.get('funding'):
        #     funding_data = dataset['funding']
        #     if isinstance(funding_data, list):
        #         # Simplify funding to just keep funder references
        #         funding_list = []
        #         for fund in funding_data:
        #             if isinstance(fund, dict):
        #                 if fund.get('funder'):
        #                     funding_list.append({'funder': fund['funder']})
        #         if funding_list:
        #             props['funding'] = funding_list
        #     else:
        #         if isinstance(funding_data, dict) and funding_data.get('funder'):
        #             props['funding'] = {'funder': funding_data['funder']}
        
        # Handle distribution - ensure each has an @id
        if dataset.get('distribution'):
            distributions = dataset['distribution']
            if not isinstance(distributions, list):
                distributions = [distributions]
            
            processed_distributions = []
            for idx, dist in enumerate(distributions):
                if isinstance(dist, dict):
                    # Ensure @id exists
                    if '@id' not in dist:
                        # Generate an @id based on contentUrl or index
                        if 'contentUrl' in dist:
                            dist_id = f"#distribution_{hash(dist['contentUrl']) & 0x7FFFFFFF}"
                        else:
                            dist_id = f"#distribution_{idx}"
                        dist['@id'] = dist_id
                    processed_distributions.append(dist)
                elif isinstance(dist, str):
                    # If it's just a URL string, convert to proper DataDownload object
                    processed_distributions.append({
                        '@id': f"#distribution_{idx}",
                        '@type': 'DataDownload',
                        'contentUrl': dist
                    })
            
            props['distribution'] = processed_distributions if len(processed_distributions) > 1 else processed_distributions[0] if processed_distributions else None
        
        # Add spatial coverage
        spatial_value = dataset.get('spatialCoverage') or dataset.get('spatial')
        if spatial_value is not None:
            props['spatialCoverage'] = spatial_value
        
        # Add copyright year
        if dataset.get('copyrightYear'):
            props['copyrightYear'] = dataset['copyrightYear']
        
        # Add measurement technique
        if dataset.get('measurementTechnique'):
            props['measurementTechnique'] = dataset['measurementTechnique']
        
        # Add other fields
        if dataset.get('conditionsOfAccess'):
            props['conditionsOfAccess'] = self._extract_first_value(dataset['conditionsOfAccess'])
        
        if dataset.get('includedInDataCatalog'):
            props['includedInDataCatalog'] = dataset['includedInDataCatalog']
        
        # Update root dataset
        for key, value in props.items():
            self.crate.root_dataset[key] = value
        
        # Create a Study from the dataset
        self._add_study_from_dataset(dataset)
    
    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitize identifier to contain only allowed characters.
        
        ARCtrl allows: letters, digits, underscore (_), dash (-), and whitespace ( )
        
        Args:
            identifier: Original identifier
            
        Returns:
            Sanitized identifier
        """
        # Replace forbidden characters with underscore
        # Common forbidden: . / : \ etc
        import re
        # Keep only alphanumeric, underscore, dash, and space
        sanitized = re.sub(r'[^a-zA-Z0-9_\- ]', '_', identifier)
        return sanitized
    
    def _add_study_from_dataset(self, dataset: Dict[str, Any]):
        """Create a Study entity from the dataset.
        
        Args:
            dataset: Dataset metadata
        """
        # Generate study ID
        identifier = dataset.get('identifier', dataset.get('@id', 'study'))
        if isinstance(identifier, list):
            identifier = identifier[0]
        if isinstance(identifier, dict):
            identifier = identifier.get('value', 'study')
        
        # Sanitize identifier for ARCtrl compatibility
        identifier = self._sanitize_identifier(identifier)
        
        study_id = f"studies/{identifier}/"
        
        name = self._extract_first_value(dataset.get('name', 'Study'))
        description = self._extract_first_value(dataset.get('description', ''))
        
        # Create Study entity
        from rocrate.model.contextentity import ContextEntity
        study_props = {
            '@type': 'Dataset',
            'additionalType': 'Study',
            'identifier': identifier,
            'name': name,
            'description': description,
        }
        
        # Add dates
        if dataset.get('dateModified'):
            study_props['dateModified'] = self._extract_first_value(dataset['dateModified'])
        
        # Add creators
        creators = []
        if dataset.get('creator'):
            creator_list = dataset['creator']
            if not isinstance(creator_list, list):
                creator_list = [creator_list]
            for creator in creator_list:
                creator_ref = self._process_creator(creator)
                if creator_ref:
                    creators.append(creator_ref)
        if dataset.get('author'):
            author_list = dataset['author']
            if not isinstance(author_list, list):
                author_list = [author_list]
            for author in author_list:
                creator_ref = self._process_creator(author)
                if creator_ref and creator_ref not in creators:
                    creators.append(creator_ref)
        
        if creators:
            study_props['creator'] = creators
        
        study_entity = ContextEntity(self.crate, study_id, properties=study_props)
        self.crate.add(study_entity)
        self.studies.append({'@id': study_id})
        
        # Create an Assay from measurement information if available
        if dataset.get('measurementTechnique') or dataset.get('keywords'):
            self._add_assay_from_dataset(dataset, study_id)
        
        # Add Study reference to Investigation hasPart
        current_haspart = self.crate.root_dataset.get('hasPart', [])
        if not isinstance(current_haspart, list):
            current_haspart = [current_haspart] if current_haspart else []
        current_haspart.append({'@id': study_id})
        self.crate.root_dataset['hasPart'] = current_haspart
    
    def _add_assay_from_dataset(self, dataset: Dict[str, Any], study_id: str):
        """Create an Assay entity from dataset measurement information.
        
        Args:
            dataset: Dataset metadata
            study_id: ID of the parent study
        """
        # Generate assay ID
        identifier = dataset.get('identifier', dataset.get('@id', 'assay'))
        if isinstance(identifier, list):
            identifier = identifier[0]
        if isinstance(identifier, dict):
            identifier = identifier.get('value', 'assay')
        
        # Sanitize identifier for ARCtrl compatibility
        identifier = self._sanitize_identifier(identifier)
        
        assay_id = f"assays/{identifier}/"
        
        from rocrate.model.contextentity import ContextEntity
        assay_props = {
            '@type': 'Dataset',
            'additionalType': 'Assay',
            'identifier': identifier,
        }
        
        # Add measurement technique
        if dataset.get('measurementTechnique'):
            meas_tech = dataset['measurementTechnique']
            if meas_tech:  # Only add if not empty
                assay_props['measurementTechnique'] = meas_tech
                assay_props['measurementMethod'] = meas_tech
        
        assay_entity = ContextEntity(self.crate, assay_id, properties=assay_props)
        self.crate.add(assay_entity)
        self.assays.append({'@id': assay_id})
        
        # Add Assay to Investigation hasPart
        current_haspart = self.crate.root_dataset.get('hasPart', [])
        if not isinstance(current_haspart, list):
            current_haspart = [current_haspart] if current_haspart else []
        current_haspart.append({'@id': assay_id})
        self.crate.root_dataset['hasPart'] = current_haspart
    
    def _process_creator(self, creator: Any) -> Optional[Dict[str, str]]:
        """Process a creator/author entity.
        
        Args:
            creator: Creator entity (Person or Organization)
            
        Returns:
            Reference to the creator entity
        """
        if isinstance(creator, dict):
            entity_type = creator.get('@type', [])
            if isinstance(entity_type, str):
                entity_type = [entity_type]
            
            # If it's a Person
            if 'Person' in entity_type:
                person_entity = self._add_person(creator)
                if person_entity:
                    return {'@id': person_entity.get('@id', '')}
            
            # If it's an Organization
            elif 'Organization' in entity_type:
                org_entity = self._add_organization(creator)
                if org_entity:
                    return {'@id': org_entity.get('@id', '')}
            
            # If it has @id already
            elif '@id' in creator:
                return {'@id': creator['@id']}
            
            # If it's just a name
            elif 'name' in creator:
                return creator
        
        elif isinstance(creator, str):
            return {'@id': creator}
        
        return None
    
    def _extract_first_value(self, value: Any) -> str:
        """Extract first value from list or return as-is.
        
        Args:
            value: Value that might be a list
            
        Returns:
            First value or original value
        """
        if isinstance(value, list) and value:
            return str(value[0])
        return str(value) if value else ''
    
    def _add_person(self, person_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add Person entity to RO-Crate.
        
        Args:
            person_data: Person metadata
            
        Returns:
            Person entity with @id
        """
        person_id = person_data.get('@id', '')
        if not person_id:
            name = person_data.get('name', '')
            if not name:
                given = person_data.get('givenName', '')
                family = person_data.get('familyName', '')
                name = f"{given}_{family}".strip('_')
            person_id = f"#Person_{name.replace(' ', '_')}"
        
        # Check if already added
        if person_id in self.added_entities:
            return self.added_entities[person_id]
        
        props = {}
        
        if person_data.get('name'):
            props['name'] = person_data['name']
        
        if person_data.get('givenName'):
            props['givenName'] = person_data['givenName']
        
        if person_data.get('familyName'):
            props['familyName'] = person_data['familyName']
        
        if person_data.get('email'):
            props['email'] = person_data['email']
        
        if person_data.get('affiliation'):
            affiliation = person_data['affiliation']
            if isinstance(affiliation, str):
                props['affiliation'] = affiliation
            else:
                props['affiliation'] = affiliation
        
        if person_data.get('identifier'):
            props['identifier'] = person_data['identifier']
        
        if person_data.get('address'):
            props['address'] = person_data['address']
        
        if person_data.get('jobTitle'):
            props['jobTitle'] = person_data['jobTitle']
        
        # Add person entity using Person class (sets @type: "Person")
        from rocrate.model.person import Person
        person_entity = Person(self.crate, person_id, properties=props)
        self.crate.add(person_entity)
        
        entity_ref = {'@id': person_id}
        self.added_entities[person_id] = entity_ref
        return entity_ref
    
    def _add_organization(self, org_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add Organization entity to RO-Crate.
        
        Args:
            org_data: Organization metadata
            
        Returns:
            Organization entity with @id
        """
        org_id = org_data.get('@id', '')
        if not org_id:
            name = org_data.get('name', 'Unknown')
            org_id = f"#Organization_{name.replace(' ', '_')[:50]}"
        
        # Check if already added
        if org_id in self.added_entities:
            return self.added_entities[org_id]
        
        props = {
            'name': org_data.get('name', ''),
        }
        
        if org_data.get('url'):
            props['url'] = org_data['url']
        
        if org_data.get('identifier'):
            props['identifier'] = org_data['identifier']
        
        if org_data.get('email'):
            props['email'] = org_data['email']
        
        if org_data.get('address'):
            props['address'] = org_data['address']
        
        if org_data.get('contactPoint'):
            props['contactPoint'] = org_data['contactPoint']
        
        # Add @type to properties for Organization
        props['@type'] = 'Organization'
        
        # Add organization entity
        from rocrate.model.contextentity import ContextEntity
        org_entity = ContextEntity(self.crate, org_id, properties=props)
        self.crate.add(org_entity)
        
        entity_ref = {'@id': org_id}
        self.added_entities[org_id] = entity_ref
        return entity_ref
    
    def _add_defined_term(self, term_data: Dict[str, Any]) -> Dict[str, str]:
        """Add DefinedTerm entity to RO-Crate.
        
        Args:
            term_data: DefinedTerm metadata
            
        Returns:
            Reference to the DefinedTerm entity
        """
        term_id = term_data.get('@id', term_data.get('identifier', f"#DefinedTerm_{term_data.get('name', 'unknown')}"))
        
        # Check if already added
        if term_id in self.added_entities:
            return self.added_entities[term_id]
        
        props = {
            'name': term_data.get('name', ''),
        }
        
        if term_data.get('identifier'):
            props['identifier'] = term_data['identifier']
        
        if term_data.get('termCode'):
            props['termCode'] = term_data['termCode']
        
        if term_data.get('inDefinedTermSet'):
            props['inDefinedTermSet'] = term_data['inDefinedTermSet']
        
        # Add DefinedTerm entity
        from rocrate.model.contextentity import ContextEntity
        term_entity = ContextEntity(self.crate, term_id, properties=props)
        self.crate.add(term_entity)
        
        entity_ref = {'@id': term_id}
        self.added_entities[term_id] = entity_ref
        return entity_ref
    
    def _add_publication(self, pub_data: Dict[str, Any]):
        """Add Publication entity to RO-Crate.
        
        Args:
            pub_data: Publication metadata
        """
        props = {
            '@type': 'ScholarlyArticle',
            '@id': pub_data.get('@id', pub_data.get('identifier', f"#pub-{pub_data.get('name', 'unknown')}")),
            'name': pub_data.get('name', ''),
        }
        
        if pub_data.get('description'):
            props['description'] = pub_data['description']
        
        if pub_data.get('identifier'):
            props['identifier'] = pub_data['identifier']
        
        if pub_data.get('url'):
            props['url'] = pub_data['url']
        
        if pub_data.get('datePublished'):
            props['datePublished'] = pub_data['datePublished']
        
        if pub_data.get('author'):
            props['author'] = self._normalize_reference(pub_data['author'])
        
        self.crate.add_jsonld(props)
    
    def _normalize_reference(self, value: Any) -> Any:
        """Normalize reference values to @id format.
        
        Args:
            value: Reference value (dict, list, or string)
            
        Returns:
            Normalized reference
        """
        if isinstance(value, dict):
            if '@id' in value:
                return {'@id': value['@id']}
            elif 'name' in value:
                # Create inline reference
                return value
        elif isinstance(value, list):
            return [self._normalize_reference(v) for v in value]
        elif isinstance(value, str):
            # Assume it's already an @id
            return {'@id': value}
        
        return value
    
    def save(self, dest_path: str):
        """Save RO-Crate to disk.
        
        Args:
            dest_path: Destination directory path
        """
        self.crate.write(dest_path)
    
    def to_json(self) -> Dict[str, Any]:
        """Export RO-Crate as JSON-LD.
        
        Returns:
            JSON-LD representation
        """
        return self.crate.metadata.generate()
