## MODIFIED Requirements

### Requirement: Print Layout Formatting
The system SHALL format the payment slips for printing, hiding UI controls and fitting exactly three slips per A4 page. The slip layout SHALL have:
- Title "НАЛОГ ЗА УПЛАТУ" centered with 2mm margins above and below
- Right-side input fields compacted to minimal height (28px)
- QR code sized at 135×135 pixels positioned below the model/reference number field
- Zero top padding on the slip container to maximize usable space
- Each slip height set to 94mm

#### Scenario: Printing slips
- **WHEN** the user triggers the browser print dialog (e.g., via a "Print" button)
- **THEN** the print controls are hidden, and the layout is adjusted to print exactly three payment slips per A4 page with 5mm margins and 1mm spacing between slips
