## Why

The spa-github-pages redirect pattern requires two components to work:
1. A `404.html` that redirects to root with the path encoded in the query string
2. A script in the main app (index.html) that decodes the query string back to the proper URL path

Without the decoder script, users would be stuck on the root URL after being redirected from 404.html. The decoder restores the original path so the SPA can route correctly.

## What Changes

- Add spa-github-pages URL decoder script to `src/index.html`
- The script SHALL check if a redirect is present in the query string (indicated by `?/`)
- The script SHALL decode the path and query parameters from the encoded format
- The script SHALL use `window.history.replaceState()` to restore the original URL without causing a page reload
- This enables the SPA to handle the route client-side after the 404 redirect

## Capabilities

### New Capabilities
- `spa-url-decoder`: Client-side script that decodes spa-github-pages redirect URLs

### Modified Capabilities
- None

## Impact

- Modified file: `src/index.html` - added decoder script in `<head>` section
- Enables proper URL restoration after 404 redirect
- Required companion to `src/404.html` redirect script
