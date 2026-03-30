## Purpose

Parse share URLs and auto-fill payment slip forms with decoded data.

## Requirements

### Requirement: URL Path Parsing
The system SHALL parse the URL path after page load to detect share URLs.

#### Scenario: User visits share URL
- **WHEN** the page loads with a URL matching `/s/v1/...` pattern
- **THEN** the system extracts the version and encoded data

### Requirement: Version-Specific Decoding
The system SHALL use the appropriate decoder based on the URL version.

#### Scenario: Version v1 URL detected
- **WHEN** the URL contains `/s/v1/`
- **THEN** the v1 decoder is used to decode the data

### Requirement: Base64 URL-Safe Decoding
The decoder SHALL reverse the base64 URL-safe encoding.

#### Scenario: Decoding encoded data
- **WHEN** processing the encoded string
- **THEN** it replaces `-` with `+`, `_` with `/`, and adds padding for base64 decode

### Requirement: Sparse Data De-sparsification
The decoder SHALL de-sparsify the data by filling in empty fields from previous slips.

#### Scenario: Processing sparse-encoded slips
- **WHEN** decoding multiple slips with sparse encoding
- **THEN** empty fields are filled with values from the previous slip

### Requirement: Form Population
The system SHALL populate the payment slip forms with decoded data.

#### Scenario: Data decoded successfully
- **WHEN** the decoder successfully decodes the data
- **THEN** the slips array is replaced with decoded slips and forms are populated

### Requirement: Error Handling
The system SHALL handle invalid or malformed share URLs gracefully.

#### Scenario: Invalid URL or data
- **WHEN** the URL is malformed, version is unsupported, or data is corrupt
- **THEN** show an error toast and continue with default empty slip
