## 1. UI Components

- [x] 1.1 Add "Share" button HTML to the payment slip control area
- [x] 1.2 Add CSS styles for the Share button (consistent with existing buttons)
- [x] 1.3 Add toast notification HTML structure (hidden by default)
- [x] 1.4 Add CSS styles for toast notification (position, animation, colors)

## 2. Data Processing

- [x] 2.1 Create function to generate QR strings for all payment slips
- [x] 2.2 Create function to merge QR strings with safe delimiter (`\n`)
- [x] 2.3 Create sparse encoding function (compare fields with previous slip, replace duplicates with empty strings)
- [x] 2.4 Create base64 URL-safe encoding function (replace `+` → `-`, `/` → `_`, remove `=` padding)

## 3. Share Functionality

- [x] 3.1 Create function to construct final URL with version prefix `/s/v1/` (origin + '/s/v1/' + encoded data)
- [x] 3.2 Implement Clipboard API copy function with error handling
- [x] 3.3 Wire up Share button click handler to trigger full share flow

## 4. Notifications

- [x] 4.1 Create toast display function with auto-dismiss (2-3 seconds)
- [x] 4.2 Show success toast on successful clipboard copy
- [x] 4.3 Show error toast with manual copy option on clipboard failure

## 5. Integration

- [x] 5.1 Import/integrate all functions into main app scope
- [x] 5.2 Test Share button with single payment slip
- [x] 5.3 Test Share button with multiple payment slips (sparse encoding)
- [x] 5.4 Verify toast notifications appear correctly
