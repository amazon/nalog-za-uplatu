## 1. Setup

- [x] 1.1 Include AlpineJS via CDN in `sample.html`
- [x] 1.2 Include Tailwind CSS via CDN in `sample.html`
- [x] 1.3 Include `qrcode.js` library script in `sample.html`

## 2. State Management

- [x] 2.1 Define AlpineJS component state (`slips` array, `showIpsCode` boolean)
- [x] 2.2 Initialize state with one empty slip

## 3. UI Refactoring

- [x] 3.1 Refactor the static slip HTML into a template loop (`x-for`) using the AlpineJS `slips` state
- [x] 3.2 Replace static text values with input fields bound to the state using `x-model` for editing
- [x] 3.3 Add an "Add payment slip" button that appends a new empty slip to the state
- [x] 3.4 Add a "Copy" button to each slip that duplicates it
- [x] 3.5 Add a "Remove" button to each slip that deletes it from the state
- [x] 3.6 Add a global toggle switch bound to `showIpsCode` state

## 4. IPS QR Integration

- [x] 4.1 Create a container for the IPS QR code on the slip layout
- [x] 4.2 Integrate `qrcode.js` to render QR codes dynamically based on slip data
- [x] 4.3 Implement Cyrillic-to-Latin transliteration for QR code encoding
- [x] 4.4 Implement account number padding to 18 digits for IPS standard compliance
- [x] 4.5 Use amount format with comma decimal separator (e.g., `RSD1234,56`)
- [x] 4.6 Use `x-show` to toggle the visibility of the QR codes based on `showIpsCode`

## 5. Styling & Print Optimization

- [x] 5.1 Apply Tailwind CSS utility classes for layout, replacing existing inline styles where appropriate
- [x] 5.2 Ensure `@media print` rules (or Tailwind `print:` modifiers) correctly hide UI controls
- [x] 5.3 Ensure print layout maintains exactly three slips per A4 page with 5mm margins and 1mm spacing (190mm x 95mm slips)
- [x] 5.4 Position title "НАЛОГ ЗА УПЛАТУ" centered with 2mm margins and minimal top padding
- [x] 5.5 Compact right-side field heights to 28px (20% reduction)
- [x] 5.6 Size QR code at 135×135 pixels with proper positioning below model/reference fields

## 6. Final Polish

- [x] 6.1 Test adding, editing, copying, and removing slips
- [x] 6.2 Test the generated IPS QR codes with a scanner app
- [x] 6.3 Test the print layout in the browser to confirm A4 pagination
