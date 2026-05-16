# Supplier Matching and Scoring

## Matching candidates
For each procurement item, FastAPI searches supplier catalogs and selects a best product candidate per supplier:
- Token match: every token (len >= 2) from the item name must appear in the product name or description.
- Availability: `available_stock >= quantity` and `minimum_order_quantity <= quantity`.
- Best product per line: lowest extended total, then lowest lead time.

A supplier is eligible only if:
- All items can be fulfilled by that supplier
- Total extended cost is within the max budget
- Delivery deadline is met (if provided)

## WLC scoring
Weighted Linear Combination (WLC):

```
Score = 0.4 * Price_Score + 0.4 * Delivery_Score + 0.2 * Reliability_Score

Price_Score       = 1 - (supplier_price / max_price_in_pool)
Delivery_Score    = 1 - (lead_time_days / max_lead_time_in_pool)
Reliability_Score = rating / 10.0
```

## Ranking tie-breaker
Suppliers are ranked by:
1. Higher WLC score
2. Lower extended total
3. Lower bottleneck lead time
4. Higher supplier id

## LLM justification
The top 3 suppliers are sent to Ollama with the justification prompt. If Ollama recommends a supplier not in the top 3 pool, FastAPI falls back to the top-ranked supplier.
