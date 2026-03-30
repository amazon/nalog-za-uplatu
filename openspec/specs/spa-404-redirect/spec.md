## Purpose

Enable SPA routing on GitHub Pages by providing a 404.html redirect page that preserves the original URL path.

## Requirements

### Requirement: 404 Redirect Page
The system SHALL provide a `404.html` file in the `src/` directory.

#### Scenario: User accesses unknown URL
- **WHEN** a user accesses a URL path that doesn't exist
- **THEN** GitHub Pages serves the 404.html file

### Requirement: SPA Redirect Script
The 404.html SHALL contain JavaScript that redirects to the root with the original path preserved.

#### Scenario: 404 page loads
- **WHEN** the 404.html page loads
- **THEN** it redirects to root URL with the original path encoded as query string

### Requirement: Path Preservation
The redirect script SHALL preserve the original path for client-side routing.

#### Scenario: Share URL accessed
- **WHEN** a user accesses `/s/v1/BASE64DATA`
- **THEN** they are redirected to `/?/s/v1/BASE64DATA` where the SPA handles the route
