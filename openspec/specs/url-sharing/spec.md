## Purpose

Enable sharing of payment slip data via generated URLs with clipboard copy and toast notifications.

## Requirements

### Requirement: Share Button Display
The system SHALL display a "Share" button in the payment slip interface, positioned near the existing action buttons (Add payment slip, Print).

#### Scenario: User views payment slips
- **WHEN** the application displays payment slips
- **THEN** a "Share" button is visible in the control area

### Requirement: Generate Share URL
The system SHALL generate a shareable URL when the user clicks the Share button. The URL SHALL contain base64-encoded sparse representation of all payment slip data.

#### Scenario: User clicks Share button
- **WHEN** the user clicks the "Share" button
- **THEN** the system generates a URL containing encoded form data

### Requirement: QR String Merging
The system SHALL construct form data by merging each payment slip's IPS QR code string using a safe delimiter that does not appear in QR data.

#### Scenario: Multiple payment slips exist
- **WHEN** generating share data with multiple slips
- **THEN** each slip's QR string is joined with a safe delimiter (`;;`)

### Requirement: Sparse Encoding
The system SHALL apply sparse encoding to reduce URL size by replacing field values that match the previous slip's corresponding field with empty strings.

#### Scenario: Duplicate field values across slips
- **WHEN** a field value (e.g., payer name) is identical to the same field in the previous slip
- **THEN** the system replaces that value with an empty string in the output

### Requirement: Base64 URL-Safe Encoding
The system SHALL encode the sparse data using base64 URL-safe encoding (replace `+` with `-`, `/` with `_`, remove `=` padding).

#### Scenario: Encoding sparse data
- **WHEN** the sparse string is ready for URL inclusion
- **THEN** the system applies base64 URL-safe encoding

### Requirement: URL Construction
The system SHALL construct the final URL by appending the encoded data to the current origin with version prefix: `/s/v1/ENCODEDDATA` (where `s` = share, `v1` = version 1).

#### Scenario: Building final URL
- **WHEN** encoding is complete
- **THEN** the system creates a URL in format `https://hostname:port/s/v1/ENCODEDDATA`

### Requirement: Clipboard Copy
The system SHALL copy the generated URL to the user's clipboard automatically.

#### Scenario: URL generation complete
- **WHEN** the URL is fully constructed
- **THEN** the system copies it to the clipboard using the Clipboard API

### Requirement: Toast Notification
The system SHALL display a toast notification confirming the URL was copied to clipboard.

#### Scenario: Successful copy
- **WHEN** the URL is successfully copied to clipboard
- **THEN** a toast message appears stating "URL copied to clipboard!"

#### Scenario: Copy failure
- **WHEN** clipboard copy fails (e.g., permission denied)
- **THEN** an error toast appears with the URL text for manual copying
