## Why

The payment slip height and IPS QR code field length limits required fine-tuning after initial implementation. The slip height was 1mm too tall, and the receiver and purpose fields in the QR string were truncated too aggressively, risking data loss for typical real-world values.

## What Changes

- Reduce `.uplatnica` CSS height from `95mm` to `94mm`
- Increase the IPS QR `P:` (receiver) field substring limit from 30 to 35 characters
- Increase the IPS QR `S:` (purpose) field substring limit from 25 to 35 characters

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `payslip-management`: Print layout height requirement updated — slip height reduced from 95mm to 94mm
- `ips-qr-integration`: QR code generation requirements updated — receiver and purpose field character limits increased to 35

## Impact

- `src/index.html`: CSS `.uplatnica` rule and IPS QR string construction logic
