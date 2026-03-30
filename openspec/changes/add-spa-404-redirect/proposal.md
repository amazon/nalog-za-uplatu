## Why

GitHub Pages is a static hosting service that returns 404 errors for unknown paths. For single-page applications (SPAs) with client-side routing (like our share URLs `/s/v1/...`), this causes problems because refreshing or visiting a deep link directly results in a 404 error.

The standard workaround is to add a `404.html` file that redirects to the main app with the original path preserved in the query string. This allows the SPA JavaScript to load and handle the route client-side.

## What Changes

- Add `src/404.html` containing the SPA GitHub Pages redirect script
- The script redirects any unmatched URL to the root with the path encoded as a query parameter
- This enables client-side routing to work correctly for share URLs like `/s/v1/BASE64DATA`

## Capabilities

### New Capabilities
- `spa-404-redirect`: 404.html redirect page that enables SPA routing on GitHub Pages

### Modified Capabilities
- None

## Impact

- New file: `src/404.html`
- Enables direct access to share URLs without 404 errors
- No changes to existing build or serve scripts required
