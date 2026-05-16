# Phase 6 — Scoring Integration & Workflow Enhancement

## Objective
Integrate the supplier scoring algorithm (WLC) into the procurement workflow and enhance the n8n automation to include scoring and LLM justification steps. This phase creates the necessary API endpoints for scoring and justification, updates the n8n workflow to use these services, and ensures seamless data flow from email extraction to PO generation with supplier selection.

## Tasks

### 1. Create Scoring API Endpoints

Create new endpoints in the FastAPI application under a new router (`scoring.py`):

#### POST /scoring/score_suppliers
- **Input**: Procurement request (same as extraction output) and list of available suppliers (from database)
- **Output**: List of scored suppliers sorted by WLC score (descending), each with:
  - Supplier ID and basic info
  - WLC score
  - Component scores (price, delivery, reliability)
- **Logic**:
  - Calculate max_price and max_lead_time from the supplier pool
  - For each supplier, compute:
    - Price_Score = 1 - (supplier_price / max_price_in_pool)
    - Delivery_Score = 1 - (lead_time_days / max_lead_time_in_pool)
    - Reliability_Score = supplier.rating / 10.0
    - WLC Score = (0.4 × Price_Score) + (0.4 × Delivery_Score) + (0.2 × Reliability_Score)
  - Handle edge cases (zero max values, missing data)
  - Return top N suppliers (default 3) or full scored list

#### POST /scoring/justification
- **Input**: 
  - Top 3 suppliers from scoring (with scores and details)
  - Procurement request (items, constraints, etc.)
- **Output**: 
  ```json
  {
    "recommended_supplier_id": integer,
    "justification": "string",
    "runner_up_supplier_id": integer or null
  }
  ```
- **Logic**:
  - Format input for LLM using the justification prompt (from `prompts/justification.txt`)
  - Call Ollama with the formatted prompt
  - Validate and return the LLM response
  - Fallback logic: if Ollama fails, return the highest-scoring supplier as recommendation

### 2. Update Orders Generation Endpoint

Modify the existing `/orders/generate` endpoint (or create if not exists) to:

- Accept a `supplier_id` parameter in the request body
- Use this supplier ID to fetch supplier details from the database
- Generate the PO for the specified supplier
- Return the generated PO details (including PDF path)

**Request Body Example**:
```json
{
  "request_id": "REQ-2026-001",
  "supplier_id": 12,
  "items": [{"product": "Laptop", "quantity": 10}],
  "constraints": {
    "max_budget": 30000.00,
    "currency": "PEN",
    "delivery_before": "2026-05-19"
  },
  "priority": "high"
}
```

### 3. Update n8n Workflow

Modify the imported workflow (`n8n/workflows/procurement_flow.json`) to include scoring and justification steps:

#### Updated Flow:
1. **IMAP Trigger** → 
2. **HTML-to-Text** → 
3. **Extract Entities** (POST `/procurement/parse`) → 
4. **Budget Check** (IF `budget_exceeded == true`) → 
   - **True Path**: Send budget alert email → End
   - **False Path**: Continue to scoring
5. **Score Suppliers** (POST `/scoring/score_suppliers`) → 
6. **Get Justification** (POST `/scoring/justification`) → 
7. **Generate PO** (POST `/orders/generate` with `supplier_id` from justification) → 
8. **Wait for Approval** (Webhook) → 
9. **Update PO Status** (PATCH `/orders/{id}/approve`) → 
10. **Send Notifications** (Email based on approval outcome)

#### Node Details:

**Score Suppliers Node**:
- Method: POST
- URL: `http://fastapi:8000/scoring/score_suppliers`
- Body: 
  ```json
  {
    "procurement_request": {{ $json }},
    "available_suppliers": [] // To be filled by a previous function node or hardcoded for testing
  }
  ```
  *Note: In practice, we'll need to fetch suppliers from the database. We can add a function node before scoring to query the suppliers table, or we can have the endpoint fetch them internally (preferred).*

**Get Justification Node**:
- Method: POST
- URL: `http://fastapi:8000/scoring/justification`
- Body:
  ```json
  {
    "top_suppliers": {{ $json[\"scored_suppliers\"] }}, // Assuming scoring returns { scored_suppliers: [...] }
    "procurement_request": {{ $previous_node.json.procurement_request }} // Or pass through
  }
  ```

**Generate PO Node**:
- Update body to include `supplier_id`:
  ```json
  {
    "request_id": {{ $json[\"request_id\"] }},
    "supplier_id": {{ $json[\"recommended_supplier_id\"] }},
    "items": {{ $json[\"items\"] }},
    "constraints": {{ $json[\"constraints\"] }},
    "priority": {{ $json[\"priority\"] }}
  }
  ```

### 4. Supplier Data Fetching for Scoring

Since the scoring endpoint needs access to the supplier catalog, we have two options:

**Option A (Preferred)**: Have the scoring endpoint fetch suppliers directly from the database.
- Create a database query inside the endpoint to get all active suppliers with their products
- This keeps the workflow simpler (no need to pass supplier list)

**Option B**: Pass supplier list from n8n via a previous node.
- Add a node before scoring that calls `GET /suppliers` to fetch the supplier catalog
- Pass the result to the scoring endpoint

We'll implement Option A for simplicity and performance.

### 5. Error Handling and Fallbacks

Implement robust error handling in the workflow:

- **Scoring Service Failure**: 
  - If scoring service is unavailable, fallback to a simple sorting (e.g., by rating or price)
  - Log error and continue with fallback ranking
  
- **Justification Service Failure**:
  - If Ollama/justification fails, use the top supplier from scoring as recommendation
  - Generate a basic justification based on scores

- **Validation Errors**:
  - Return appropriate HTTP status codes (400 for bad input, 503 for service unavailable)
  - n8n should handle these via error workflows or continue with fallbacks

### 6. Update Data Flow Between Nodes

Ensure proper data passing between nodes using n8n's expression language:

- After entity extraction, pass the full JSON to the budget check and scoring nodes
- After scoring, pass the scored suppliers list to the justification node
- After justification, extract the `recommended_supplier_id` to pass to the PO generation node
- Preserve the original procurement request data throughout for use in justification and PO generation

### 7. Unit and Integration Tests

Create tests for the new components:

- **Scoring endpoint tests**:
  - Test WLC calculations with known values
  - Test edge cases (zero prices, missing lead times)
  - Test sorting and top supplier selection

- **Justification endpoint tests**:
  - Test with mock Ollama responses
  - Test fallback behavior when Ollama fails

- **Workflow tests** (conceptual):
  - Verify data flows correctly between nodes
  - Check that supplier ID is correctly passed to PO generation

### 8. Documentation and Comments

- Add docstrings to all new API endpoints
- Update the project README or documentation to reflect the new scoring integration
- Add inline comments in the n8n workflow JSON for complex expressions

## Deliverables

By the end of this phase, the project must include:

- New `scoring.py` router in `backend/routers/` with `/scoring/score_suppliers` and `/scoring/justification` endpoints
- Updated `orders.py` router to accept `supplier_id` in the generation endpoint
- Modified `n8n/workflows/procurement_flow.json` with scoring and justification nodes
- Updated database queries in scoring endpoint to fetch supplier catalog
- Unit tests for scoring logic and API endpoints
- Integration tests showing the flow: email → extraction → scoring → justification → PO generation → approval

## Technical Expectations

### API Design
- Follow existing FastAPI patterns in the project
- Use Pydantic models for request/response validation
- Return appropriate HTTP status codes
- Handle database sessions properly (dependency injection)
- Log important events and errors

### Scoring Algorithm
- Implement WLC exactly as specified in AGENTS.md §11
- Use Decimal for monetary calculations to avoid floating-point errors
- Normalize scores to 0-1 range where higher is better
- Handle division by zero gracefully

### Workflow Integration
- Use Docker internal hostnames (`fastapi:8000`) for all service calls
- Set appropriate timeouts (scoring: 10s, justification: 30s, PO generation: 15s)
- Ensure data types are preserved between nodes (especially IDs and monetary values)
- Add error handling nodes for critical paths

### Performance
- Scoring endpoint should be optimized for reasonable supplier pools (<100 suppliers)
- Database queries should use indexes on relevant columns (e.g., supplier.active)
- Avoid N+1 queries when fetching supplier/product data

### Security
- Validate all inputs to scoring and justification endpoints
- Sanitize any user-provided data used in LLM prompts to prevent injection
- Ensure supplier data accessed is only active/approved suppliers

## Success Criteria

1. `docker compose up -d` starts all services without errors
2. New scoring endpoints return correct WLC scores for test data
3. Justification endpoint returns valid JSON recommendations
4. n8n workflow correctly routes:
   - Budget-exceeded emails to alert path
   - Normal emails through scoring → justification → PO generation → approval
5. Generated PO includes the correct supplier ID from the justification step
6. Approval webhook updates PO status to 'Approved' when approved
7. Unit tests pass for scoring calculations and endpoint validation
8. Integration test validates the full flow with a sample procurement email
9. Fallback behavior works when scoring/justification services are unavailable
10. No regression in existing functionality (email extraction, budget alerts)

## Example Scoring Calculation (Reference)

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

## Next Steps After Phase 6

Once the scoring integration is complete, proceed to:
- Phase 7: Enhance PDF generation with dynamic branding and legal compliance features
- Phase 8: Add advanced analytics and reporting capabilities
- Phase 9: Implement multi-currency support and international procurement features
- Phase 10: Production hardening, monitoring, and alerting setup