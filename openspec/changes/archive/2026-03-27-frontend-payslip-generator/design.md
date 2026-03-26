## Context

The current `sample.html` file contains hardcoded HTML elements for a Serbian payment slip (Nalog za uplatu). It lacks dynamic capabilities, forcing users to manually edit the HTML to generate slips with different data. The goal is to create a dynamic, single-page application (SPA) that can generate these slips on the fly without needing a backend server, and can be hosted on GitHub Pages.

## Goals / Non-Goals

**Goals:**
- Create a fully frontend-based payment slip generator.
- Implement a reactive UI using AlpineJS for managing a list of payment slips.
- Use Tailwind CSS via CDN for rapid UI styling, replacing the current inline/internal CSS while keeping print optimizations intact.
- Integrate the `qrcode.js` library to dynamically render IPS QR codes based on slip data, with Cyrillic-to-Latin transliteration for proper encoding.
- Provide a print-friendly layout that hides UI controls and properly paginates the slips (e.g., exactly three slips per printed A4 page with 5mm margins and 1mm spacing). Layout includes centered title with minimal 2mm margins, compacted right-side input fields (28px height), and enlarged 135×135 pixel QR code.

**Non-Goals:**
- Backend data persistence (no database). Data will only live in the current browser session (or optionally local storage, though not strictly required for MVP).
- Authentication or user accounts.
- Complex build steps (Node.js, Webpack, Vite). We want to keep it simple with CDN links to maintain the lightweight nature of the existing repository, making it trivially publishable to GitHub Pages.

## Decisions

- **AlpineJS for State Management**: Chosen because it is extremely lightweight, can be included via a simple CDN `<script>` tag, and avoids the need for a complex build system like React or Vue would typically require. It's perfectly suited for adding reactivity to an existing HTML structure.
- **Tailwind CSS via CDN**: Chosen for ease of styling without a build step. While the CDN version is larger and not recommended for heavy production apps, it's acceptable for a simple, single-page utility tool hosted on GitHub Pages. We will use arbitrary values or a custom config in the script tag if needed for specific print styles.
- **IPS QR Code Generation**: We will use the `qrcode.js` library for rendering QR codes. Serbian Cyrillic text will be transliterated to ASCII Latin characters before encoding to ensure QR code compatibility and reduce data size. Account numbers will be padded to 18 digits as required by the IPS standard.
- **Data Structure**: The AlpineJS state will hold an array of `slips` objects. Each object will contain properties corresponding to the fields on a payment slip (payer, purpose, receiver, amount, account number, etc.).
- **Print Layout**: We will retain the existing CSS `@media print` rules from `sample.html` or translate them into Tailwind's `print:` modifiers to ensure the exact dimensions and page breaks are preserved for A4 printing.

## Risks / Trade-offs

- **Risk: Print layout inconsistencies across different browsers.** → Mitigation: We will stick closely to the proven CSS dimensions (mm) and `@page` rules already present in `sample.html` which are known to work.
- **Trade-off: Using Tailwind CDN.** → Mitigation: It increases the initial page load slightly compared to a compiled CSS file, but significantly simplifies the development and deployment process for this small utility.
- **Risk: IPS QR code generation failure if the data format is incorrect.** → Mitigation: Transliterate Cyrillic to ASCII, pad account numbers to 18 digits, and ensure the UI clearly shows if the QR code fails to render.
