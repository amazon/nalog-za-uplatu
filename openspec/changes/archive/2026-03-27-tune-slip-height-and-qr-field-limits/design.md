## Context

The payment slip component (`.uplatnica`) and IPS QR code string builder are defined in `src/index.html`. After the initial implementation, two issues were identified through visual inspection and testing:

1. The slip height of `95mm` caused layout overflow when fitting three slips per A4 page.
2. The IPS QR string builder truncated the receiver (`P:`) field at 30 characters and the purpose (`S:`) field at 25 characters — limits that are too short for common real-world values.

## Goals / Non-Goals

**Goals:**
- Reduce `.uplatnica` height by 1mm (95mm → 94mm) to fit the three-per-page A4 print layout correctly
- Increase the IPS QR `P:` (receiver) field character limit from 30 to 35
- Increase the IPS QR `S:` (purpose) field character limit from 25 to 35

**Non-Goals:**
- Changes to any other CSS properties or slip dimensions
- Changes to mandatory QR fields (account number, amount, currency, etc.)
- Changes to the QR string format or library

## Decisions

**Height: 95mm → 94mm**
A single 1mm reduction was sufficient to resolve the overflow. No other layout properties were changed.

**Field limits: receiver 30→35, purpose 25→35**
Both limits raised to 35 to align with common real-world string lengths for recipient names and payment purposes in the Serbian payment system. The IPS QR standard allows longer values; the previous limits were conservative estimates.

## Risks / Trade-offs

- **QR code size**: Longer field values produce a denser QR code, which may be harder to scan at the 135×135px render size. → Mitigation: Limits remain well below the IPS standard maximum; the density increase is negligible at these lengths.
