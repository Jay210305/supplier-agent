# PDF Generation

## Service
The PDF generator uses WeasyPrint to create a purchase order PDF from HTML.

## Output location
- Container path: `/app/generated_pos`
- Stored DB path: `generated_pos/<filename>`

## File naming
```
PO_<request_id>_<YYYYMMDD_HHMMSS>.pdf
```

## Totals
The PDF includes totals in PEN:
- Subtotal (sum of quantity * unit_price)
- IGV 18%
- Grand total

## Included fields
The document includes:
- PO number (request_id)
- Date
- Supplier name, RUC, and email
- Item table with quantity, unit price, and line totals
- Subtotal, IGV, total
