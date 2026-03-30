#!/bin/bash

# Run Jekyll locally for GitHub Pages testing
# 
# This script starts a local Jekyll server with live reload for testing
# your GitHub Pages site before deploying.
#
# Requirements:
#   - Ruby (installed)
#   - Bundler (gem install bundler)
#   - Jekyll and GitHub Pages gems (installed via bundle)
#
# For more information, see GitHub's documentation:
# https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/testing-your-github-pages-site-locally-with-jekyll

# Start Jekyll server with live reload
echo ""
echo "Starting Jekyll server with live reload..."
echo "Site will be available at: http://localhost:4000"
echo ""
jekyll serve --source src/ --livereload --host 0.0.0.0
