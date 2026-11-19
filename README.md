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
- **Optional compressed sharing**: Share links remain backward compatible with
  `/s/v1/`, while the opt-in `/s/v2/` format embeds an IPQ2-compressed IPS batch

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
│   ├── index.html          # Main application page
│   ├── llms.txt            # Machine-readable context for AI models & agents
│   ├── main.ts             # Browser module entry point
│   ├── share-links.ts      # v1 and optional IPQ2 v2 share links
│   └── ipq2/               # Browser-compatible IPQ2 codec
├── doc/
│   ├── agents.md           # Instructions for AI assistants (ChatGPT, Gemini, DeepSeek, etc.)
│   └── share-link-formats-and-compression.md # Detailed specification of share links & codecs
├── llms.txt                # Root copy of AI context file
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
- **zstdify** - Browser-compatible Zstandard codec with raw dictionary support
- **esbuild** - TypeScript browser bundling

## Deployment

This remains a static frontend application with no backend. Compile the
embedded vocabulary and browser module before serving it:

```bash
npm ci
npm run build
jekyll serve --source src/
```

GitHub Pages should run `npm run build` before the Jekyll build.

## Serbian IPS QR Code Format

The QR codes follow the NBS (Nacionalna banka Srbije) IPS standard:
- Format: `K:PR|V:01|C:1|R:account|N:payer|I:RSDamount|P:receiver|SF:code|S:purpose|RO:reference`
- Account numbers are padded to 18 digits
- Cyrillic characters are transliterated to ASCII Latin
- Amount uses comma as decimal separator (e.g., `RSD1234,56`)

## Share Link Formats & Compression

The application supports generating sharable URLs containing multi-slip payment batches:

- **Legacy v1 Links (`/s/v1/<payload>`)**:
  - The default backward-compatible format.
  - Applies line-by-line field deduplication (**sparsification**), omitting fields that match the preceding slip.
  - Encodes the resulting sparse UTF-8 text as URL-safe Base64 without padding.
  - Requires no WebAssembly or external decoders.

- **Compressed v2 Links (`/s/v2/<payload>`)**:
  - Activated using the **"Short link (IPQ2)"** checkbox.
  - Compresses the canonical IPS batch using **IPQ2** (Zstandard level 19 with a 32 KB domain dictionary and vocabulary tokenization).
  - Encodes the resulting binary archive as URL-safe Base64 without padding.
  - Reduces URL lengths by **~63%** on typical 4-slip tax batches (646 characters down to 242 characters), preventing URLs from exceeding chat or browser limits on larger batches.

### Underlying Compression Codecs

- **IPQ1** ([IPQ1.md](IPQ1.md)): Specialized domain codec using 7-trit field-state delta encoding, zigzag integers, move-to-front text caches, packed 6-bit reference codes, and raw DEFLATE with a preset Serbian payment dictionary.
- **IPQ2** ([IPQ2.md](IPQ2.md)): Evolution of IPQ1 using Zstandard dictionary compression, a 2,831-term word-boundary token table derived from Serbian and English payment terms, an 8-byte vocabulary integrity fingerprint, and 3 adaptive representation modes (raw text, semantic, and tokenized semantic).

For the complete technical specification of both wire formats and compression pipelines, see [doc/share-link-formats-and-compression.md](doc/share-link-formats-and-compression.md).

## AI Assistant & Agent Integration

The application is designed to be agent-friendly:

- **[`llms.txt`](llms.txt)**: Provides a machine-readable entry point per the [llms.txt standard](https://llmstxt.org).
- **[`doc/agents.md`](doc/agents.md)**: Comprehensive guidelines and prompt templates for ChatGPT, Gemini, DeepSeek, and Google Search AI mode to parse invoices and generate working `/s/v1/` multi-slip links.
- **Direct Link Generation**: Because `/s/v1/` uses text-based sparsification and standard Base64URL, any LLM can construct valid payment links directly without executing complex compression libraries.


