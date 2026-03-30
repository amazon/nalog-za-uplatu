## ADDED Requirements

### Requirement: Default Payment Slip
The system SHALL display a single empty payment slip on load, ready for user input.

#### Scenario: Application load
- **WHEN** the application loads
- **THEN** the system displays one empty payment slip with blank fields

### Requirement: Add New Payment Slip
The system SHALL allow users to add a new, empty payment slip to the list.

#### Scenario: Adding a new slip
- **WHEN** the user clicks the "Add payment slip" button
- **THEN** a new, empty payment slip is appended to the list

### Requirement: Copy Existing Payment Slip
The system SHALL allow users to duplicate an existing payment slip.

#### Scenario: Duplicating a slip
- **WHEN** the user clicks the "Copy" button on a specific payment slip
- **THEN** a new payment slip with the exact same data is created and appended directly below the copied slip

### Requirement: Remove Payment Slip
The system SHALL allow users to remove a payment slip from the list.

#### Scenario: Removing a slip
- **WHEN** the user clicks the "Remove" button on a specific payment slip
- **THEN** the payment slip is removed from the list

### Requirement: Edit Payment Slip Data
The system SHALL allow users to edit the data fields of any payment slip.

#### Scenario: Editing fields
- **WHEN** the user focuses on an input field (payer, purpose, receiver, payment code, currency, amount, account receiver, model, reference number) and types
- **THEN** the value is updated immediately and reflected in the UI and state

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
