## 1. URL Parsing

- [x] 1.1 Add function to detect share URL pattern (`/s/v1/...`)
- [x] 1.2 Extract version and encoded data from URL path
- [x] 1.3 Run URL check after page load (Alpine.js init)

## 2. Decoding Functions

- [x] 2.1 Implement base64 URL-safe decode function
- [x] 2.2 Implement v1 decoder with sparse data de-sparsification
- [x] 2.3 Parse QR string format back to slip objects

## 3. Form Population

- [x] 3.1 Replace slips array with decoded data
- [x] 3.2 Handle single slip vs multiple slips
- [x] 3.3 Ensure form inputs update with new data

## 4. Error Handling

- [x] 4.1 Add validation for malformed URLs
- [x] 4.2 Show error toast for unsupported versions
- [x] 4.3 Fallback to default empty slip on decode failure

## 5. Testing

- [x] 5.1 Test with valid v1 share URL
- [x] 5.2 Test with malformed URL
- [x] 5.3 Test with unsupported version
- [x] 5.4 Verify forms populate correctly
