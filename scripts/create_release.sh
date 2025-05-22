#!/bin/bash

# Script to create a new release of the Lyo backend

# Exit on error
set -e

# Check if version is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.0"
    exit 1
fi

VERSION=$1
CURRENT_DATE=$(date +"%Y-%m-%d")

echo "Creating release $VERSION..."

# Check if git is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "Error: Git working directory is not clean. Commit or stash changes first."
    exit 1
fi

# Update version in main.py
sed -i '' "s/version=\"[0-9]\+\.[0-9]\+\.[0-9]\+\"/version=\"$VERSION\"/" main.py

# Update version in OpenAPI documentation
sed -i '' "s/version=\"[0-9]\+\.[0-9]\+\.[0-9]\+\"/version=\"$VERSION\"/" api/core/docs.py

# Create a CHANGELOG entry
if [ ! -f "CHANGELOG.md" ]; then
    echo "# Changelog" > CHANGELOG.md
    echo "" >> CHANGELOG.md
fi

# Insert new release at the top
sed -i '' "1i\\
# Changelog\\
\\
## $VERSION ($CURRENT_DATE)\\
\\
### Added\\
- <Add new features>\\
\\
### Changed\\
- <Add changes in existing functionality>\\
\\
### Fixed\\
- <Add bug fixes>\\
\\
### Security\\
- <Add security improvements>\\
\\
" CHANGELOG.md

# Open editor to update changelog
if [ -n "$EDITOR" ]; then
    $EDITOR CHANGELOG.md
else
    vi CHANGELOG.md
fi

# Commit changes
git add main.py api/core/docs.py CHANGELOG.md
git commit -m "Release version $VERSION"

# Create tag
git tag -a "v$VERSION" -m "Release version $VERSION"

echo "Release $VERSION created successfully!"
echo "Run 'git push && git push --tags' to push to remote repository."
