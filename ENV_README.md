# Environment Configuration Templates

This directory contains environment configuration templates for different deployment targets.

## Files

- **`.env.dev`** - Development environment (datahub-dev.ipk-gatersleben.de)
- **`.env.prod`** - Production environment (git.nfdi4plants.org)
- **`.env`** - Active configuration (defaults to dev, not tracked in git)
- **`.env.example`** - Template with placeholder values

## Setup

1. Copy the appropriate template to `.env`:
   ```bash
   # For development
   cp .env.dev .env
   
   # For production
   cp .env.prod .env
   ```

2. Update the values in `.env` with your credentials

3. Alternatively, use the `--env` flag to specify a config file:
   ```bash
   python scripts/gitlab_submit.py <arc_directory> --env .env.prod
   ```

## Configuration Variables

- `GITLAB_URL`: GitLab instance URL
- `GITLAB_PRIVATE_TOKEN`: Personal access token with API access
- `GITLAB_NAMESPACE_ID`: Namespace/group ID for projects
- `GITLAB_GROUP_ID`: Group ID (usually same as namespace ID)

## Security

⚠️ **Never commit actual credentials to git!**

All `.env*` files (except `.env.example`) are ignored by git to prevent accidentally committing sensitive credentials.
