## Purpose

Decode spa-github-pages redirect URLs in the main application to restore the original URL path for client-side routing.

## Requirements

### Requirement: URL Decoder Script
The system SHALL include a spa-github-pages URL decoder script in `src/index.html`.

#### Scenario: Page loads with redirect query string
- **WHEN** index.html loads with a query string starting with `/`
- **THEN** the decoder script executes

### Requirement: Query String Detection
The script SHALL detect spa-github-pages encoded URLs.

#### Scenario: Encoded URL present
- **WHEN** the URL contains `?/` (query string starting with `/`)
- **THEN** the script identifies it as a spa-github-pages redirect

### Requirement: Path Decoding
The script SHALL decode the encoded path and parameters.

#### Scenario: Decoding redirect URL
- **WHEN** processing `?/s/v1/BASE64DATA`
- **THEN** it decodes `~and~` back to `&` and reconstructs the original query string

### Requirement: URL Restoration
The script SHALL restore the original URL without page reload.

#### Scenario: URL restoration
- **WHEN** decoding is complete
- **THEN** it calls `window.history.replaceState()` to update the URL in the browser history

### Requirement: Script Placement
The script SHALL be placed in the `<head>` section before the SPA framework loads.

#### Scenario: Page initialization
- **WHEN** index.html is parsed
- **THEN** the decoder script runs before Alpine.js initializes
