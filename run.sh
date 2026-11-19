#!/bin/bash

set -euo pipefail

# Run Jekyll locally for GitHub Pages testing
# 
# This script starts a local Jekyll server with live reload for testing
# your GitHub Pages site before deploying.
#
# Requirements:
#   - Node.js and npm (npm install)
#   - Ruby (installed)
#   - Bundler (gem install bundler)
#   - Jekyll and GitHub Pages gems (installed via bundle)
#
# For more information, see GitHub's documentation:
# https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/testing-your-github-pages-site-locally-with-jekyll

# Build the embedded vocabulary and browser TypeScript bundle
echo ""
echo "Building browser assets..."
npm run build

# Start Jekyll server with live reload
echo ""
echo "Starting Jekyll server with live reload..."
echo "Site will be available at: http://localhost:4000"
echo ""
exec jekyll serve --source src/ --livereload --host 0.0.0.0
