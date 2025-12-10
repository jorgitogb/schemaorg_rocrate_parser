"""
GitLab submission module for ARC repositories.

This module handles the submission of ARC (Annotated Research Context) 
directories to GitLab repositories using the GitLab API.
"""

import os
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
import gitlab
from dotenv import load_dotenv


class GitLabSubmitter:
    """Handle ARC submission to GitLab repositories."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize GitLab submitter with configuration.
        
        Args:
            config_path: Path to .env file. If None, loads from current directory.
        """
        # Load environment variables
        if config_path:
            load_dotenv(config_path)
        else:
            load_dotenv()
        
        # Get configuration from environment
        self.gitlab_url = os.getenv('GITLAB_URL')
        self.private_token = os.getenv('GITLAB_PRIVATE_TOKEN')
        self.namespace_id = os.getenv('GITLAB_NAMESPACE_ID')
        self.group_id = os.getenv('GITLAB_GROUP_ID')
        
        # Validate required configuration
        if not all([self.gitlab_url, self.private_token, self.namespace_id]):
            raise ValueError(
                "Missing required GitLab configuration. "
                "Please set GITLAB_URL, GITLAB_PRIVATE_TOKEN, and GITLAB_NAMESPACE_ID "
                "in your .env file."
            )
        
        # Convert namespace_id to int (already validated as non-None)
        self.namespace_id = int(self.namespace_id)  # type: ignore
        
        # Initialize python-gitlab client
        self.gl = gitlab.Gitlab(url=self.gitlab_url, private_token=self.private_token)
    
    def _sanitize_project_name(self, name: str) -> str:
        """
        Sanitize project name for GitLab compatibility.
        
        GitLab has restrictions on project names. This method ensures
        the name is valid by converting to lowercase and replacing
        special characters with hyphens.
        
        Args:
            name: Original project name
            
        Returns:
            Sanitized project name
        """
        import re
        # Convert to lowercase, replace spaces and special chars with hyphens
        sanitized = re.sub(r'[^a-z0-9_-]', '-', name.lower())
        # Remove consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        # Limit length (GitLab has a 255 char limit)
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip('-')
        return sanitized
    
    def create_project(self, name: str, description: str = "", 
                      visibility: str = "private",
                      topics: list[str] | None = None) -> Dict[str, Any]:
        """
        Create a new GitLab project.
        
        Args:
            name: Project name (will be sanitized for GitLab)
            description: Project description
            visibility: Project visibility (private, internal, public)
            topics: List of topics/tags for the project
        
        Returns:
            Project data from GitLab API
        """
        # Sanitize the project name for GitLab path
        sanitized_name = self._sanitize_project_name(name)
        
        # Use python-gitlab library which handles topics correctly
        project_params = {
            "name": name,  # Keep original name as display name
            "path": sanitized_name,  # Use sanitized name as path
            "description": description,
            "namespace_id": self.namespace_id,
            "visibility": visibility,
            "initialize_with_readme": False
        }
        
        # Add topics if provided
        if topics:
            project_params["topics"] = topics
        
        try:
            project = self.gl.projects.create(project_params)
            
            # Return as dict for compatibility
            return project.attributes
        except Exception as e:
            print(f"Error creating project: {e}")
            raise
    
    def update_project_topics(self, project_id: int, topics: list[str]) -> Dict[str, Any]:
        """
        Update topics/tags for a GitLab project.
        
        Args:
            project_id: GitLab project ID
            topics: List of topics/tags to set
        
        Returns:
            Response from GitLab API
        """
        try:
            # Use python-gitlab library
            project = self.gl.projects.get(project_id)
            project.topics = topics
            project.save()
            
            # Refresh to get updated data
            project = self.gl.projects.get(project_id)
            return {"topics": project.attributes.get('topics', [])}
            
        except Exception as e:
            print(f"Warning: Failed to update topics: {e}")
            return {}
    
    def upload_avatar(self, project_id: int, avatar_path: Path) -> Dict[str, Any]:
        """
        Upload an avatar/logo for a GitLab project.
        
        Args:
            project_id: GitLab project ID
            avatar_path: Path to avatar image file
        
        Returns:
            Response from GitLab API
        """
        try:
            # Use python-gitlab library to set avatar
            project = self.gl.projects.get(project_id)
            with open(avatar_path, 'rb') as avatar_file:
                project.avatar = avatar_file
                project.save()
            return {"avatar_url": project.attributes.get("avatar_url")}
        except Exception as e:
            print(f"Warning: Failed to upload avatar: {e}")
            # Don't raise - avatar upload is not critical
            return {}
    
    def project_exists(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if a project exists in the namespace.
        
        Args:
            project_name: Name of the project to check (will be sanitized)
        
        Returns:
            Project data if exists, None otherwise
        """
        try:
            # Search for project by name
            projects = self.gl.projects.list(search=project_name, owned=True)
            
            # Look for exact name match
            for project in projects:
                if project.attributes['name'] == project_name:
                    return project.attributes
            
            return None
            
        except Exception as e:
            print(f"Error checking if project exists: {e}")
            return None
    
    def upload_file(self, project_id: int, file_path: Path, 
                   repo_path: str, branch: str = "main",
                   commit_message: str = "Add file") -> Dict[str, Any]:
        """
        Upload a single file to GitLab repository.
        
        Args:
            project_id: GitLab project ID
            file_path: Local path to file
            repo_path: Path in repository where file should be stored
            branch: Branch name
            commit_message: Commit message
        
        Returns:
            Response from GitLab API
        """
        # Read file content and encode to base64
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        
        data = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": "base64",
            "file_path": repo_path
        }
        
        project = self.gl.projects.get(project_id)
        result = project.files.create(data)
        return {"file_path": repo_path, "branch": branch}
    
    def upload_directory(self, project_id: int, directory: Path, 
                        branch: str = "main",
                        commit_message: str = "Add ARC structure") -> None:
        """
        Upload an entire directory structure to GitLab in a single commit.
        
        Args:
            project_id: GitLab project ID
            directory: Local directory to upload
            branch: Branch name
            commit_message: Commit message for all files
        """
        # Collect all files to upload (including subdirectories)
        files_to_upload = []
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                # Skip Excel temp files only (keep .gitkeep and other hidden files)
                if file_path.name.startswith('~$'):
                    continue
                # Get relative path from directory
                relative_path = file_path.relative_to(directory)
                files_to_upload.append((file_path, str(relative_path).replace('\\', '/')))
        
        # Sort files to ensure .gitkeep files are created first to establish directory structure
        files_to_upload.sort(key=lambda x: (0 if x[1].endswith('.gitkeep') else 1, x[1]))
        
        print(f"Uploading {len(files_to_upload)} files to GitLab in a single commit...")
        
        # Prepare actions for commit API
        actions = []
        for local_path, repo_path in files_to_upload:
            # Read file content and encode to base64
            with open(local_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            
            actions.append({
                "action": "create",
                "file_path": repo_path,
                "content": content,
                "encoding": "base64"
            })
        
        # Use Commits API to upload all files in one commit
        data = {
            "branch": branch,
            "commit_message": commit_message,
            "actions": actions
        }
        
        try:
            project = self.gl.projects.get(project_id)
            project.commits.create(data)
            print(f"  ✓ Successfully committed {len(files_to_upload)} files")
        except Exception as e:
            print(f"  ✗ Failed to commit files: {e}")
            raise
    
    def submit_arc(self, arc_directory: Path, project_name: Optional[str] = None,
                   description: str = "", overwrite: bool = False,
                   branch: str = "main",
                   topics: list[str] | None = None,
                   avatar_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Submit an ARC directory to GitLab.
        
        Args:
            arc_directory: Path to ARC directory
            project_name: GitLab project name (defaults to directory name)
            description: Project description
            overwrite: If True, delete and recreate existing project
            branch: Branch name to commit to (default: main)
            topics: List of topics/tags for the project
            avatar_path: Path to avatar/logo image file (optional)
        
        Returns:
            Project information
        """
        if not arc_directory.exists():
            raise FileNotFoundError(f"ARC directory not found: {arc_directory}")
        
        # Use directory name as project name if not specified
        if project_name is None:
            project_name = arc_directory.name
        
        print(f"Submitting ARC to GitLab: {project_name}")
        
        # Check if project exists
        existing_project = self.project_exists(project_name)
        
        if existing_project:
            if not overwrite:
                raise ValueError(
                    f"Project '{project_name}' already exists in GitLab. "
                    "Use overwrite=True to replace it."
                )
            print(f"  Deleting existing project: {project_name}")
            self.delete_project(existing_project['id'])
        
        # Create new project
        print(f"  Creating GitLab project: {project_name}")
        if topics:
            print(f"  Topics: {', '.join(topics)}")
        
        # Create project (topics in params may be ignored on some GitLab versions)
        project = self.create_project(
            name=project_name,
            description=description,
            visibility="private",
            topics=topics  # Try to set during creation
        )
        
        print(f"  ✓ Project created: {project['web_url']}")
        
        # Check which topics were actually set
        if topics:
            actual_topics = project.get('topics', [])
            if actual_topics:
                print(f"  ✓ Topics set: {', '.join(actual_topics)}")
                # Warn if not all topics were set (GitLab may have a limit)
                if len(actual_topics) < len(topics):
                    missing = set(topics) - set(actual_topics)
                    print(f"  ⚠ Note: {len(missing)} topic(s) not set (GitLab may have a limit): {', '.join(missing)}")
            else:
                print(f"  ⚠ Topics not set - this may be a GitLab permission or configuration issue")
                print(f"    Requested: {', '.join(topics)}")
        
        # Upload avatar if provided
        if avatar_path and avatar_path.exists():
            print(f"  Uploading avatar: {avatar_path.name}")
            self.upload_avatar(project['id'], avatar_path)
            print(f"  ✓ Avatar uploaded")
        
        # Create branch if not main
        if branch != "main":
            print(f"  Creating branch: {branch}")
            try:
                project_obj = self.gl.projects.get(project['id'])
                project_obj.branches.create({'branch': branch, 'ref': 'main'})
                print(f"  ✓ Branch created: {branch}")
            except Exception as e:
                # Branch might already exist
                if "already exists" not in str(e).lower():
                    print(f"  ⚠ Branch creation warning: {e}")
        
        # Upload ARC directory
        self.upload_directory(
            project_id=project['id'],
            directory=arc_directory,
            branch=branch,
            commit_message="Add ARC structure"
        )
        
        print("\n✓ ARC submitted successfully!")
        print(f"  Project URL: {project['web_url']}")
        print(f"  Project ID: {project['id']}")
        
        return project
    
    def delete_project(self, project_id: int) -> None:
        """
        Delete a GitLab project.
        
        Args:
            project_id: GitLab project ID
        """
        project = self.gl.projects.get(project_id)
        project.delete()
