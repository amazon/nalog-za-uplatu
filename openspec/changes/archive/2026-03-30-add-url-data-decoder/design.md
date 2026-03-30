## Context

The share URL feature encodes payment slip data as base64 URL-safe strings. When a user visits a share URL like `/s/v1/BASE64DATA`, we need to:
1. Parse the URL to extract version and encoded data
2. Decode the data using the version-specific decoder
3. Populate the forms with the decoded payment slip data

The encoding uses sparse encoding (replacing repeated fields with empty strings), so the decoder must handle de-sparsification.

## Goals / Non-Goals

**Goals:**
- Parse share URLs after page load to extract encoded data
- Decode data using version-specific decoders
- Populate payment slip forms dynamically
- Support multiple versions (starting with v1)

**Non-Goals:**
- Server-side URL handling
- Modifying the share URL format
- Persisting decoded data beyond the session

## Decisions

**Timing: Run after page fully loads**
- Wait for DOM ready and Alpine.js initialization
- Rationale: Need the form elements and Alpine.js to be ready

**Version dispatch: Pattern matching on URL**
- Extract version from `/s/v{version}/...` pattern
- Rationale: Allows easy extension for future versions

**Decoding approach: Reverse the encoding steps**
- Base64 URL-safe decode (replace `-` with `+`, `_` with `/`, add padding)
- Split by newlines to get individual slip data
- De-sparsify by filling in empty fields from previous slip
- Parse QR string format back to slip objects

**Integration: Extend existing Alpine.js component**
- Add initialization logic to `paymentSlips()` component
- Rationale: Forms are already managed by Alpine.js

## Risks / Trade-offs

- **Invalid URL handling** → Gracefully ignore malformed URLs, show error toast
- **Large data sets** → May cause UI freeze; use reasonable limits
- **Version mismatch** → Show error for unsupported versions
