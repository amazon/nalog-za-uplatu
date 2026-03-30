## Context

GitHub Pages doesn't support true SPA routing - any URL path that doesn't match a physical file returns a 404 error. This breaks client-side routing for share URLs like `/s/v1/BASE64DATA`. The standard workaround is to add a `404.html` file that redirects to the main app with the original path preserved in the query string.

## Goals / Non-Goals

**Goals:**
- Add a 404.html redirect page that enables SPA routing on GitHub Pages
- Preserve the original path in the query string for client-side handling
- Support direct access to share URLs without 404 errors

**Non-Goals:**
- Implementing true server-side routing
- Modifying GitHub Pages behavior
- Complex build pipelines or CI/CD

## Decisions

**Approach: SPA GitHub Pages redirect script**
- Use the well-known `spa-github-pages` redirect pattern (MIT License)
- The 404.html contains JavaScript that redirects to root with the path encoded in query string
- Rationale: Minimal, proven solution, no build step required

**Path encoding**
- Original path `/s/v1/BASE64DATA` becomes `?/s/v1/BASE64DATA`
- Query parameters are preserved with `~and~` encoding
- Rationale: GitHub Pages handles query strings on root URL, allowing SPA to parse and route

**pathSegmentsToKeep = 0**
- For custom domain deployment (not Project Pages)
- Rationale: Repository is configured for custom domain use

## Risks / Trade-offs

- **SEO implications** - 404 pages return redirect script instead of content → Mitigation: Search engines index the canonical URLs; SPA handles routing
- **Flash of 404** - User briefly sees blank page before redirect → Mitigation: Standard trade-off for SPA GitHub Pages hosting; redirect is fast
- **IE compatibility** - Script must be >512 bytes for IE → Mitigation: Comments in script bring it over 512 bytes
