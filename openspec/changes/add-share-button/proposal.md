## Why

Users need a way to share their payment slip data with others or save it for later use. Currently, there's no mechanism to export or share the form state. A shareable URL would allow users to easily transfer their payment information without re-entering data manually.

## What Changes

- Add a "Share" button to the payment slip interface
- On click, generate a URL containing base64-encoded sparse form data for all payment slips
- Form data is constructed by merging QR code strings with a safe delimiter
- The data is "sparsed" by replacing duplicate field values (same as previous form) with empty strings
- The resulting string is base64 URL-safe encoded
- The encoded data is appended to the base URL in format `https://hostname:port/s/v1/BASE64DATA` where `s` = share, `v1` = data format version 1, and BASE64DATA is the encoded sparse string
- The full URL is copied to the clipboard
- Display a toast notification to confirm the URL was copied
- **Scope exclusion**: URL decoding and form prefilling is NOT included in this change

## Capabilities

### New Capabilities
- `url-sharing`: Share payment slip data via generated URLs with clipboard copy and toast notifications

### Modified Capabilities
- `payslip-management`: Add Share button to the payment slip UI

## Impact

- `src/index.html`: Add Share button, implement URL generation logic, add toast notification UI
