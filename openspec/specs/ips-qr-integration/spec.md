## ADDED Requirements

### Requirement: Toggle IPS QR Code
The system SHALL provide a global toggle to show or hide the IPS QR code on all generated payment slips.

#### Scenario: Toggling IPS code visibility
- **WHEN** the user switches the "IPS code" toggle
- **THEN** all payment slips either show or hide their respective IPS QR code

### Requirement: Generate IPS QR Code
The system SHALL generate an IPS QR code for each payment slip based on its current data. When building the QR string, optional text fields SHALL be truncated to the following limits:
- Receiver (`P:`) — maximum 35 characters
- Purpose (`S:`) — maximum 35 characters

#### Scenario: Rendering QR code
- **WHEN** the IPS code toggle is enabled and valid data is present in a slip
- **THEN** the system renders an IPS QR code in the designated area on the slip using the `ips-qr-code` library

#### Scenario: Handling invalid data
- **WHEN** the data in a slip is invalid or incomplete (e.g., missing account number, amount)
- **THEN** the system fails gracefully, either showing an error message or an empty box where the QR code would be
