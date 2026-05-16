# Phase 4 — Scoring & PDF Generation

## Objective
Implement the supplier scoring algorithm using Weighted Linear Combination (WLC) and the PDF generation service for Purchase Orders. This phase creates the backend services that evaluate suppliers based on price, delivery time, and reliability, then generates formatted PDF POs in Peruvian Soles (PEN) using WeasyPrint.

## Tasks

### 1. Create Supplier Scoring Service

Create `backend/services/scoring.py` with:

- Implementation of the Weighted Linear Combination (WLC) algorithm as specified in AGENTS.md §11
- Functions to calculate Price_Score, Delivery_Score, and Reliability_Score
- Logic to find max_price_in_pool and max_lead_time_in_pool from supplier candidates
- Method to rank suppliers and return top 3 for LLM justification
- Integration with existing supplier and product data models
- Proper handling of edge cases (zero values, missing data)

Key requirements:
- Price_Score = 1 - (supplier_price / max_price_in_pool)
- Delivery_Score = 1 - (lead_time_days / max_lead_time_in_pool)
- Reliability_Score = supplier.rating / 10.0
- Final Score = (0.4 × Price_Score) + (0.4 × Delivery_Score) + (0.2 × Reliability_Score)
- Handle cases where max values are zero to avoid division by zero
- Return suppliers sorted by score descending

### 2. Create PDF Generation Service

Create `backend/services/pdf_generator.py` with:

- WeasyPrint-based PDF generation for Purchase Orders
- Template-based approach using HTML/CSS that converts to PDF
- Integration with PurchaseOrder model data
- Proper formatting including:
  - Header with company/logo information
  - PO number and date
  - Supplier information (name, RUC, contact)
  - Itemized table with product, quantity, unit price, total
  - Totals section (subtotal, taxes if applicable, total in PEN)
  - Footer with terms and conditions
- Configuration for page size, margins, fonts
- Error handling for template rendering and PDF generation
- Storage of generated PDFs in the designated volume (`po_pdfs`)

Key requirements:
- Use WeasyPrint library (already in requirements.txt)
- Generate PDFs in PEN currency as specified
- Include all required PO fields from the purchase_orders table
- Follow Peruvian invoicing standards where applicable
- Save PDFs to the `/app/generated_pos` directory (mounted volume)
- Return the file path for database storage

### 3. Integrate Scoring with Procurement Workflow

Update relevant components to use the scoring service:

- Modify the orders generation flow to:
  1. Receive validated procurement request from `/procurement/parse`
  2. Query eligible suppliers based on items requested
  3. Score suppliers using WLC algorithm
  4. Select top 3 suppliers
  5. Send to Ollama for justification using the `prompts/justification.txt` template
  6. Generate PO PDF for the recommended supplier
  7. Store PO record with status Pending

- Ensure proper data flow between:
  - Procurement request (items, constraints)
  - Supplier/product catalog data
  - Scoring results
  - LLM justification
  - PDF generation

### 4. Add Supporting Functions

Create helper functions for:

- Currency conversion (if needed for multi-currency support)
- Date calculations for delivery timelines
- Data validation for scoring inputs
- Template context preparation for PDF generation
- Logging and audit trail integration

## Deliverables

By the end of this phase, the project must include:

- `backend/services/scoring.py` - WLC scoring algorithm implementation
- `backend/services/pdf_generator.py` - WeasyPrint PDF generation service
- Updated order generation workflow that uses scoring and PDF services
- Proper integration with existing procurement request parsing
- Storage of generated PDFs in the designated volume
- Unit tests for scoring logic and PDF generation

## Technical Expectations

### Code Quality
- Follow existing code patterns in the backend/services directory
- Proper type hints throughout
- Separation of concerns (scoring logic vs data access)
- Environment variable configuration where needed
- Comprehensive error handling and logging

### Scoring Specifics
- Uses SQLAlchemy models from Phase 2 for supplier/product data
- Handles edge cases like zero or missing values
- Performance-optimized for reasonable supplier pools
- Returns clear, sortable scores with tie-breaking logic
- Works with the seeded supplier data from Phase 2

### PDF Generation Specifics
- Uses WeasyPrint with proper HTML/CSS templates
- Generates professional-looking POs suitable for business use
- Includes all legally required fields for Peruvian POs
- Optimized for fast generation (important for workflow efficiency)
- Handles special characters and formatting correctly
- Respects page margins and ensures content fits properly

### Integration Points
- Depends on validated ProcurementRequest from Phase 3
- Uses supplier/product data seeded in Phase 2
- Works with existing Alembic migrations
- Prepares for order approval workflows (future phases)
- Compatible with n8n workflow automation

### WeasyPrint Configuration
- ANTIALIAS flag for better text rendering
- Proper font handling (consider system fonts)
- CSS for print media optimization
- Image embedding if logos are included
- UTF-8 encoding for special characters

## Success Criteria

1. `docker compose up -d` starts all services without errors
2. Scoring algorithm correctly calculates WLC scores for test data
3. Top supplier selection works correctly when deadline is binding constraint
4. PDF generation creates valid, readable Purchase Orders in PEN
5. Generated PDFs contain all required fields:
   - PO number/request_id
   - Supplier name and RUC
   - Itemized list with quantities and prices
   - Totals in PEN currency
   - Date and validity information
6. PDFs are saved to the correct volume location and paths stored in DB
7. Unit tests pass for scoring edge cases and PDF generation
8. Integration test shows full flow: email → extraction → scoring → justification → PDF generation

## Example Scoring Calculation

Given three suppliers for laptops:
- Supplier A: Price = 2500 PEN, Lead Time = 2 days, Rating = 8.0
- Supplier B: Price = 3000 PEN, Lead Time = 1 day, Rating = 9.0
- Supplier C: Price = 2800 PEN, Lead Time = 3 days, Rating = 7.0

With max_price = 3000, max_lead_time = 3:
- Supplier A: Price_Score = 1-(2500/3000)=0.167, Delivery_Score = 1-(2/3)=0.333, Reliability_Score = 8.0/10=0.8
  Score = (0.4×0.167)+(0.4×0.333)+(0.2×0.8) = 0.067+0.133+0.16 = 0.36
- Supplier B: Price_Score = 1-(3000/3000)=0, Delivery_Score = 1-(1/3)=0.667, Reliability_Score = 9.0/10=0.9
  Score = (0.4×0)+(0.4×0.667)+(0.2×0.9) = 0+0.267+0.18 = 0.447
- Supplier C: Price_Score = 1-(2800/3000)=0.067, Delivery_Score = 1-(3/3)=0, Reliability_Score = 7.0/10=0.7
  Score = (0.4×0.067)+(0.4×0)+(0.2×0.7) = 0.027+0+0.14 = 0.167

Ranking: B (0.447) > A (0.36) > C (0.167)