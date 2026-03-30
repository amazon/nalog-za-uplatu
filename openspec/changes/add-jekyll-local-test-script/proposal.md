## Why

To test GitHub Pages site locally before deploying, we need a convenient way to run Jekyll. While GitHub provides documentation for manual commands, having a simple `run.sh` script reduces friction and ensures consistent local testing across different environments.

## What Changes

- Add a `run.sh` script to the repository root
- The script SHALL build and serve the `src/` directory using Jekyll (assumes `jekyll` is in PATH)
- The script SHALL use live reload for automatic page refresh during development
- The script SHALL output the local URL (typically http://localhost:4000)
- Follow the official GitHub Pages Jekyll testing guide: https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/testing-your-github-pages-site-locally-with-jekyll

## Capabilities

### New Capabilities
- `local-jekyll-server`: Convenient script to run and test GitHub Pages site locally

### Modified Capabilities
- None

## Impact

- New file: `run.sh` in repository root
- Jekyll generates `_site/` directory during local serving (added to `.gitignore`)
- Requires Jekyll to be installed and available in PATH (documented in script comments)
