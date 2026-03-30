## Why

The share URL feature allows users to generate encoded URLs containing payment slip data. However, when a user visits a share URL, the data is not automatically loaded into the forms. We need to add functionality to parse the URL path, decode the encoded data using the appropriate version decoder, and dynamically fill the payment slip forms.

This completes the share URL workflow: generate → share → visit → auto-fill.

## What Changes

- Add a URL data decoder that runs after the page fully loads
- The decoder SHALL parse the URL path to extract version and encoded data (e.g., `/s/v1/BASE64DATA`)
- The decoder SHALL use the version-specific decode function to decode the data
- The decoder SHALL populate the payment slip forms with the decoded data
- The system SHALL support version `v1` decoder initially

## Capabilities

### New Capabilities
- `url-data-decoder`: Parse share URLs and auto-fill payment slip forms

### Modified Capabilities
- None

## Impact

- Modified file: `src/index.html` - adds URL parsing and form population logic
- Enables complete share URL workflow
- No breaking changes to existing functionality
