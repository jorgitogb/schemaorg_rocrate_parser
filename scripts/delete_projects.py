#!/usr/bin/env python3
"""
Delete GitLab projects by group or topic.

This script allows you to delete multiple GitLab projects at once, either:
- All projects in a specific group/namespace
- All projects with a specific topic
- Projects matching both group AND topic criteria

Use with caution! Projects are permanently deleted.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import gitlab
from dotenv import load_dotenv
import os


class ProjectDeleter:
    """Handle deletion of GitLab projects."""
    
    def __init__(self):
        """Initialize GitLab connection."""
        load_dotenv()
        
        self.gitlab_url = os.getenv('GITLAB_URL')
        self.private_token = os.getenv('GITLAB_PRIVATE_TOKEN')
        
        if not all([self.gitlab_url, self.private_token]):
            raise ValueError(
                "Missing GitLab configuration. "
                "Please set GITLAB_URL and GITLAB_PRIVATE_TOKEN in .env"
            )
        
        self.gl = gitlab.Gitlab(url=self.gitlab_url, private_token=self.private_token)
        print(f"✓ Connected to GitLab: {self.gitlab_url}\n")
    
    def get_projects_by_group(self, group_id: int) -> List:
        """
        Get all projects in a specific group/namespace.
        
        Args:
            group_id: GitLab group/namespace ID
            
        Returns:
            List of project objects
        """
        try:
            group = self.gl.groups.get(group_id)
            projects = group.projects.list(all=True)
            return projects
        except Exception as e:
            print(f"Error: Group {group_id} not found - {e}")
            return []
    
    def get_projects_by_topic(self, topic: str, group_id: Optional[int] = None) -> List:
        """
        Get all projects with a specific topic.
        
        Args:
            topic: Topic/tag to search for
            group_id: Optional group ID to limit search
            
        Returns:
            List of project objects
        """
        search_params = {'topic': topic, 'owned': True}
        projects = self.gl.projects.list(**search_params, all=True)
        
        # Filter by group if specified
        if group_id is not None:
            projects = [p for p in projects if p.namespace['id'] == group_id]
        
        return projects
    
    def get_all_owned_projects(self) -> List:
        """
        Get all projects owned by the current user.
        
        Returns:
            List of project objects
        """
        return self.gl.projects.list(owned=True, all=True)
    
    def delete_projects(self, projects: List, dry_run: bool = True) -> int:
        """
        Delete a list of projects.
        
        Args:
            projects: List of project objects to delete
            dry_run: If True, only show what would be deleted
            
        Returns:
            Number of projects deleted (or that would be deleted)
        """
        if not projects:
            print("No projects found matching criteria.")
            return 0
        
        print(f"Found {len(projects)} project(s):\n")
        
        # Display project information
        for i, project in enumerate(projects, 1):
            # Get full project details to access topics
            full_project = self.gl.projects.get(project.id)
            topics = full_project.attributes.get('topics', [])
            topics_str = f"[{', '.join(topics)}]" if topics else "[no topics]"
            
            print(f"{i}. {project.name}")
            print(f"   ID: {project.id}")
            print(f"   Path: {project.path_with_namespace}")
            print(f"   Topics: {topics_str}")
            print(f"   URL: {project.web_url}")
            print()
        
        if dry_run:
            print("=" * 80)
            print("DRY RUN MODE - No projects were deleted")
            print("Run with --confirm to actually delete these projects")
            print("=" * 80)
            return len(projects)
        
        # Confirm deletion
        print("=" * 80)
        print("WARNING: This will PERMANENTLY delete these projects!")
        print("=" * 80)
        response = input(f"\nType 'DELETE' to confirm deletion of {len(projects)} project(s): ")
        
        if response != 'DELETE':
            print("Deletion cancelled.")
            return 0
        
        # Delete projects
        deleted_count = 0
        print("\nDeleting projects...\n")
        
        for project in projects:
            try:
                print(f"Deleting: {project.name} (ID: {project.id})... ", end='')
                # Need to get full project object before deleting
                full_project = self.gl.projects.get(project.id)
                full_project.delete()
                print("✓ Deleted")
                deleted_count += 1
            except Exception as e:
                print(f"✗ Failed: {e}")
        
        print(f"\n✓ Deleted {deleted_count} of {len(projects)} project(s)")
        return deleted_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete GitLab projects by group or topic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all projects in group 55 (dry run)
  %(prog)s --group 55
  
  # Delete all projects with topic 'edal'
  %(prog)s --topic edal --confirm
  
  # Delete projects in group 55 with topic 'test'
  %(prog)s --group 55 --topic test --confirm
  
  # Delete all owned projects (use with caution!)
  %(prog)s --all --confirm
  
  # List all owned projects
  %(prog)s --all
        """
    )
    
    # Selection criteria
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--group',
        type=int,
        help='Delete projects in this group/namespace ID'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Delete all owned projects (use with caution!)'
    )
    
    parser.add_argument(
        '--topic',
        type=str,
        help='Delete only projects with this topic/tag'
    )
    
    # Execution mode
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Actually delete projects (default is dry-run mode)'
    )
    
    args = parser.parse_args()
    
    try:
        deleter = ProjectDeleter()
        
        # Get projects based on criteria
        if args.all:
            print("Fetching all owned projects...\n")
            projects = deleter.get_all_owned_projects()
            
            # Filter by topic if specified
            if args.topic:
                print(f"Filtering by topic: {args.topic}\n")
                projects = [p for p in projects 
                           if args.topic in deleter.gl.projects.get(p.id).attributes.get('topics', [])]
        else:
            if args.topic:
                print(f"Fetching projects in group {args.group} with topic '{args.topic}'...\n")
                projects = deleter.get_projects_by_topic(args.topic, args.group)
            else:
                print(f"Fetching all projects in group {args.group}...\n")
                projects = deleter.get_projects_by_group(args.group)
        
        # Delete (or dry-run)
        dry_run = not args.confirm
        deleter.delete_projects(projects, dry_run=dry_run)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
