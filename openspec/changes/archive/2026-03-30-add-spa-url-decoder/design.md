## Context

The spa-github-pages pattern consists of two scripts working together:
1. `404.html` - redirects unmatched URLs to root with path encoded as query string
2. `index.html` - decodes the query string back to the proper URL path

When a user accesses `/s/v1/BASE64DATA`, the 404.html redirects to `/?/s/v1/BASE64DATA`. The decoder script in index.html must then restore the original URL so the SPA can route correctly.

## Goals / Non-Goals

**Goals:**
- Decode spa-github-pages redirect URLs back to proper paths
- Restore original URL without causing page reload
- Enable SPA client-side routing after 404 redirect

**Non-Goals:**
- Handling non-spa-github-pages query strings
- Server-side URL rewriting
- Modifying browser history beyond the redirect case

## Decisions

**Detection: Check for `?/` pattern**
- Look for query string starting with `/` (e.g., `?/s/v1/...`)
- Rationale: This is the spa-github-pages encoding signature

**Decoding algorithm**
- Split query string by `&` to separate path from parameters
- Replace `~and~` with `&` in each segment (reverses 404.html encoding)
- Join path segments back with `/`
- Join parameters back with `?`
- Rationale: Exact reverse of the encoding done in 404.html

**URL restoration: `window.history.replaceState()`**
- Use replaceState to update URL without triggering navigation
- Preserves the hash fragment
- Rationale: SPA needs the correct URL in history for routing

**Script placement: In `<head>` before app loads**
- Must run before Alpine.js initializes
- Ensures correct URL is in place when app starts
- Rationale: SPA routing depends on correct initial URL

## Risks / Trade-offs

- **Race condition with SPA framework** - If script runs after Alpine.js initializes, routing may use wrong URL → Mitigation: Place script in `<head>` before Alpine.js
- **Conflicts with other query strings** - Normal query strings not from spa-github-pages could be misinterpreted → Mitigation: Only processes query strings starting with `/`
