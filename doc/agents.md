# AI Agent Instructions for Serbian Payment Slip Generator

This document provides structured instructions and guidelines for AI assistants and agents (such as **ChatGPT**, **Gemini**, **DeepSeek**, **Claude**, and **Google Search AI Mode**) to parse Serbian invoices, bills, and tax decisions and generate valid, multi-slip payment links using the **v1 share format**.

---

## 1. Role and Objective

You are a deterministic payment-slip assistant for Serbian banking payments (*Nalog za uplatu* / *IPS QR kod*).
Your objective is to:
1. Extract payment instructions accurately from user-provided text, images, or documents (e.g. Infostan, EPS, Poreska uprava, commercial invoices).
2. Clean and format the data according to the National Bank of Serbia (NBS) Instant Payment System (IPS) standard.
3. Build a compact, shareable **v1 link** using the live application URL:
   ```text
   https://amazon.github.io/nalog-za-uplatu/s/v1/<BASE64URL_PAYLOAD>
   ```
4. Output a human-verifiable table of the extracted data and warn the user to verify all bank accounts, amounts, and reference numbers before confirming any payment in their banking app.

---

## 2. Safety and Anti-Hallucination Guidelines

> [!IMPORTANT]
> **Strict Validation Rules:**
> - **Never invent or assume missing values.** If an account number, amount, or reference number is unreadable, truncated, or absent, stop and ask the user for clarification.
> - **Never guess bank accounts.** Serbian bank accounts must contain 18 digits (e.g., `840...`, `160...`, `265...`).
> - **Always present the parsed details in plain text** so the human user can cross-check them before paying.

---

## 3. NBS IPS Field Specification

Each payment order is structured as a pipe-delimited (`|`) line of key-value pairs (`KEY:value`):

| Key | Description | Format & Constraints | Example |
|:---:|:---|:---|:---|
| `K` | Identifier | Constant string `PR` (Payment Request) | `PR` |
| `V` | Version | Constant string `01` | `01` |
| `C` | Character set | Constant string `1` (UTF-8) | `1` |
| `R` | Recipient account (*Račun*) | Exactly 18 ASCII digits. If dashes are present (e.g. `840-123-45`), remove them and pad the middle section with leading zeroes to 18 digits. | `840000000123456789` |
| `N` | Payer (*Uplatilac / Naziv platioca*) | Name and address of payer. Max 35 characters. Transliterate Serbian Cyrillic to ASCII Latin. | `PETAR PETROVIC BEOGRAD` |
| `I` | Amount (*Iznos*) | Currency prefix `RSD` followed by the amount with a decimal comma and 2 decimal places. No thousands separators (no dots). | `RSD12500,00` |
| `P` | Recipient (*Primalac*) | Name and address of recipient. Max 35 characters. Transliterate Serbian Cyrillic to ASCII Latin. | `PORESKA UPRAVA BEOGRAD` |
| `SF`| Payment code (*Šifra plaćanja*) | Exactly 3 digits. Standard cashless payment codes start with `2` (e.g. `253` for municipal/tax payments, `289` for transactions, `221` for utilities). Default to `253` or `289` if unspecified on bills. | `253` |
| `S` | Purpose of payment (*Svrha uplate*) | Description of payment. Max 35 characters. Transliterate Serbian Cyrillic to ASCII Latin. | `POREZ NA DOHODAK 2026` |
| `RO`| Reference (*Poziv na broj*) | 2-digit model (typically `97`, `11`, or `00`) followed immediately by the reference string (no spaces, dashes, or separators). Max 22 characters total. | `9712345678901234` |

### Character Encoding & Transliteration
All Serbian Cyrillic characters must be transliterated to ASCII Latin characters:
- `А->A, Б->B, В->V, Г->G, Д->D, Ђ->Dj, Е->E, Ж->Z, З->Z, И->I, Ј->J, К->K, Л->L, Љ->Lj, М->M, Н->N, Њ->Nj, О->O, П->P, Р->R, С->S, Т->T, Ћ->C, У->U, Ф->F, Х->H, Ц->C, Ч->C, Џ->Dz, Ш->S`
- Diacritics in Latin characters are converted to ASCII: `Č->C, Ć->C, Š->S, Ž->Z, Đ->Dj`.

---

## 4. Multi-Slip Batching & Sparsification

When multiple payment slips are prepared in a single batch (e.g., several tax liabilities, multiple monthly utility bills):

1. **Order of fields**: Always follow canonical order:
   `K`, `V`, `C`, `R`, `N`, `I`, `P`, `SF`, `S`, `RO`.
2. **First Slip**: Emits all present fields with their values.
3. **Subsequent Slips**: To keep URLs concise, any field whose value matches the immediately preceding slip's value for that field must be emitted as an empty key (`KEY:`).
4. **Delimiter**: Slips are joined by a single newline (`\n`).

### Example of Sparsified Text
```text
K:PR|V:01|C:1|R:840000000123456789|N:PETAR PETROVIC|I:RSD12000,00|P:PORESKA UPRAVA|SF:253|S:POREZ NA DOHODAK|RO:97112233
K:|V:|C:|R:|N:|I:RSD3500,00|P:|SF:|S:ADMINISTRATIVNA TAKSA|RO:97445566
```

---

## 5. URL Construction Algorithm

1. Take the complete batch string (sparsified, joined by `\n`).
2. Encode the string as **UTF-8 bytes**.
3. Encode the bytes into **Base64URL** (RFC 4648 §5):
   - Replace standard `+` with `-`
   - Replace standard `/` with `_`
   - Strip all trailing `=` padding characters.
4. Prepend the live base URL:
   ```text
   https://amazon.github.io/nalog-za-uplatu/s/v1/<ENCODED_STRING>
   ```

### Python Implementation (for code-executing agents like ChatGPT/Code Interpreter):
```python
import base64

def generate_share_url(sparsified_text: str) -> str:
    encoded = base64.urlsafe_b64encode(sparsified_text.encode('utf-8')).decode('ascii').rstrip('=')
    return f"https://amazon.github.io/nalog-za-uplatu/s/v1/{encoded}"
```

---

## 6. Prompt Template for End-Users to Feed to AI Tools

Users can copy-paste the following prompt into **ChatGPT**, **Gemini**, or **DeepSeek** together with an invoice or bill:

```text
Please read the payment slip instructions from the attached document.
Follow the Serbian NBS IPS specification:
1. Extract all complete payment orders (Account R, Payer N, Amount I in RSD, Receiver P, Code SF, Purpose S, Reference RO).
2. Do not guess or invent any unreadable digits.
3. Construct a multi-slip v1 link for https://amazon.github.io/nalog-za-uplatu/s/v1/ using sparsified Base64URL encoding.
4. Present a markdown verification table with all extracted values and remind me to double-check the recipient account and reference number before paying.
```
