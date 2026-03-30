## Purpose

Provide a convenient script to run and test GitHub Pages site locally using Jekyll.

## Requirements

### Requirement: Script Presence
The system SHALL provide a `run.sh` script in the repository root for local Jekyll testing.

#### Scenario: Developer wants to test locally
- **WHEN** a developer wants to run the GitHub Pages site locally
- **THEN** a `run.sh` script is available in the repository root

### Requirement: Jekyll Serve
The system SHALL build and serve the Jekyll site from the `src/` directory using the `jekyll` command (assumed to be in PATH).

#### Scenario: Site serving
- **WHEN** the script is executed
- **THEN** the script runs `jekyll serve --source src/` with live reload enabled

### Requirement: Output URL
The system SHALL output the local server URL for easy access.

#### Scenario: Server starts
- **WHEN** Jekyll server starts successfully
- **THEN** the script displays the local URL (http://localhost:4000)

### Requirement: Live Reload
The system SHALL enable live reload for automatic page refresh during development.

#### Scenario: File changes
- **WHEN** source files are modified
- **THEN** the browser automatically refreshes to show changes
