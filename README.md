## Payment Slip Generator

A frontend-only web application for generating Serbian payment slips (Nalog za uplatu) for the tax authority. The app runs entirely in the browser and can be easily hosted on GitHub Pages.

## Features

- **Dynamic Slip Management**: Add, copy, edit, and remove payment slips
- **IPS QR Code Generation**: Generate scannable IPS QR codes for each slip
  - Cyrillic text is automatically transliterated to Latin for QR compatibility
  - Account numbers are padded to 18 digits per IPS standard
  - Amount format uses comma decimal separator
- **Print Optimized Layout**: Exactly 3 slips fit on a single A4 page
  - 5mm page margins with 1mm spacing between slips
  - UI controls are hidden when printing
  - Enlarged 135×135 pixel QR codes for better scanning
- **Responsive Design**: Clean, professional layout using Tailwind CSS

## Usage

1. Open `src/index.html` in any modern web browser
2. Fill in payment slip details (payer, purpose, receiver, amount, account number, etc.)
3. Click **"Add payment slip"** to create additional slips
4. Click **"Copy"** on any slip to duplicate it
5. Toggle **"IPS code"** to show/hide QR codes on all slips
6. Click **"Print Slips"** to generate a print-ready page

## File Structure

```
├── src/
│   └── index.html          # Main application file
└── openspec/
    └── changes/
        └── frontend-payslip-generator/
            ├── proposal.md
            ├── design.md
            ├── tasks.md
            └── specs/
                └── payslip-management/
                    └── spec.md
```

## Used Libraries

- **Tailwind CSS** (https://tailwindcss.com/) - Utility-first CSS framework
- **AlpineJS** (https://alpinejs.dev/) - Lightweight JavaScript framework for reactivity
- **QRCode.js** (https://github.com/davidshimjs/qrcodejs) - QR code generation library

## Deployment

This is a static frontend application. Simply host the files on any static web server or GitHub Pages. No build step or backend server is required.

## Serbian IPS QR Code Format

The QR codes follow the NBS (Nacionalna banka Srbije) IPS standard:
- Format: `K:PR|V:01|C:1|R:account|N:payer|I:RSDamount|P:receiver|SF:code|S:purpose|RO:reference`
- Account numbers are padded to 18 digits
- Cyrillic characters are transliterated to ASCII Latin
- Amount uses comma as decimal separator (e.g., `RSD1234,56`)
