## Why

The current process for generating payment slips for the Serbian tax authority requires manual HTML editing or using non-dynamic templates. A frontend-only, interactive web application is needed to allow users to easily add, copy, and configure payment slips (including IPS QR codes) directly in the browser, making the process faster and more user-friendly. Since it's a frontend-only app, it can be easily hosted on GitHub Pages.

## What Changes

- Convert the static HTML payment slip template (`sample.html`) into a dynamic, interactive frontend application.
- Integrate AlpineJS for state management and interactivity.
- Integrate Tailwind CSS for styling.
- Integrate an IPS QR code generator to display standard IPS QR codes on the slips.
- Add functionality to add new empty payment slips.
- Add functionality to copy (duplicate) existing payment slips.
- Add a global toggle to show/hide the IPS QR code on all generated payment slips.
- Ensure the print layout is optimized (e.g., hiding controls, 3 slips per page).

## Capabilities

### New Capabilities
- `payslip-management`: Ability to create, edit, duplicate, and manage multiple payment slips in a single view.
- `ips-qr-integration`: Generation and toggling of IPS QR codes for each payment slip.

### Modified Capabilities

## Impact

- `sample.html` will be refactored to include AlpineJS directives, dynamic data binding, and Tailwind utility classes.
- Dependencies (Tailwind CSS, AlpineJS, IPS QR code generator script) will be integrated.
- The repository will be configured/ready for GitHub Pages deployment.
