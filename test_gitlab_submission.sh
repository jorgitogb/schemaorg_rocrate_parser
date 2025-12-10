#!/bin/bash
# Test script for GitLab submission with topics and avatar

set -e

echo "================================================================================"
echo "GitLab Submission Test - Topics and Avatar"
echo "================================================================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create a .env file with your GitLab credentials:"
    echo ""
    echo "GITLAB_URL=https://your-gitlab-instance.com"
    echo "GITLAB_PRIVATE_TOKEN=your_token_here"
    echo "GITLAB_NAMESPACE_ID=your_namespace_id"
    echo ""
    echo "You can copy from .env.example:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your actual credentials"
    echo ""
    exit 1
fi

echo "✓ Found .env file"
echo ""

# Show available logos
echo "Available logos in assets/:"
ls -1 assets/*.png | sed 's/^/  - /'
echo ""

# Test with example_edal.json (has logo + keywords)
echo "Testing with example_edal.json:"
echo "  - Source: edal"
echo "  - Logo: assets/edal.png"
echo "  - Keywords: Pollen Embryogenese, Hordeum vulgare, Mikrosporen, Proteinanalyse"
echo ""

read -p "Press Enter to submit to GitLab (or Ctrl+C to cancel)..."
echo ""

# Run the batch processor with GitLab submission enabled
uv run scripts/batch_processor.py examples/ --file example_edal.json --submit

echo ""
echo "================================================================================"
echo "✓ Test completed!"
echo "================================================================================"
echo ""
echo "Check your GitLab instance to verify:"
echo "  1. Project was created"
echo "  2. Topics/tags were added (edal, fairagro, keywords...)"
echo "  3. Avatar/logo was set"
echo ""
