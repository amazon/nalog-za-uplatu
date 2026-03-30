## Context

The payment slip application currently allows users to create and manage multiple payment slips with full CRUD operations and print formatting. Each slip contains data fields (payer, purpose, receiver, payment code, currency, amount, account, model, reference) that can be edited. The IPS QR code generation already creates structured strings from this data. Users need a way to share their configured slips with others without manual data re-entry.

## Goals / Non-Goals

**Goals:**
- Add a Share button to the payment slip UI that triggers URL generation
- Generate a shareable URL containing sparse-encoded form data for all payment slips
- Use QR code strings as the base data format with safe delimiter merging
- Implement sparse encoding: replace duplicate field values (same as previous form) with empty strings
- Base64 URL-safe encode the sparse data
- Copy the generated URL to clipboard automatically
- Show a toast notification confirming successful copy

**Non-Goals:**
- URL decoding and form prefilling (out of scope for this change)
- Server-side storage of shared data
- Password protection or encryption of shared data
- Short URL generation
- Social media sharing integrations

## Decisions

**Data Format: QR Code Strings with Delimiter**
- Use the existing IPS QR string format as the base representation for each slip
- Join multiple slip strings with `\n` delimiter that cannot appear in QR data, because all the form fields are guaranteed to not contain newlines
- Rationale: Reuses proven serialization logic, maintains compatibility with banking standards

**Sparse Encoding Strategy**
- For each slip after the first, compare each field value to the corresponding field in the previous slip
- If values match, replace with empty string in the output
- Store field order implicitly (same as QR string field order)
- Rationale: Significant URL length reduction when multiple slips share common data (same payer, similar amounts, etc.)

**Encoding: Base64 URL-Safe**
- Use `btoa()` with URL-safe alphabet (replace `+` with `-`, `/` with `_`, remove `=` padding)
- Rationale: Standard URL-safe encoding, no special characters that need escaping in URLs

**URL Structure**
- Format: `https://hostname:port/s/v1/BASE64DATA` where `s` = share endpoint, `v1` = data format version 1, and BASE64DATA is the encoded sparse string
- Version prefix allows future format changes without breaking existing shared links
- No query parameters to keep URLs clean and cache-friendly
- Rationale: Simple structure with versioning for forward compatibility, works with static hosting

**Toast Notification**
- Use a simple CSS-based toast that appears briefly (2-3 seconds) at top-center
- No external dependencies
- Rationale: Minimal implementation, no library overhead

## Risks / Trade-offs

- **URL Length**: With many slips or long values, URLs could exceed browser limits (~2000 chars) or be truncated by email clients. → Mitigation: Sparse encoding helps; document limitations.
- **Data Loss on Copy**: Users might not notice if clipboard copy fails (permissions, etc.). → Mitigation: Toast only shows on successful copy; error handling shows alternative (manual select).
- **No Validation**: Shared URLs could contain malformed data when decoded later. → Mitigation: Validation will be part of the decoding change (future scope).
- **Versioning**: The `/s/v1/` prefix ensures future format changes can be detected and handled appropriately by decoders. → Mitigation: Version is explicit in URL path.
