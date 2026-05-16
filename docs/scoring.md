# Emparejamiento y scoring

## Matching de candidatos
Para cada item de procurement, FastAPI busca en catalogos y elige el mejor producto por proveedor:
- Token match: cada token (len >= 2) del item debe aparecer en el nombre o descripcion del producto.
- Disponibilidad: `available_stock >= quantity` y `minimum_order_quantity <= quantity`.
- Mejor producto por linea: menor total extendido, luego menor lead time.

Un proveedor es elegible solo si:
- Puede cubrir todos los items
- El total extendido esta dentro del presupuesto
- Cumple con la fecha limite (si existe)

## WLC
Weighted Linear Combination (WLC):

```
Score = 0.4 * Price_Score + 0.4 * Delivery_Score + 0.2 * Reliability_Score

Price_Score       = 1 - (supplier_price / max_price_in_pool)
Delivery_Score    = 1 - (lead_time_days / max_lead_time_in_pool)
Reliability_Score = rating / 10.0
```

## Desempate
Orden de ranking:
1. Mayor WLC
2. Menor total extendido
3. Menor lead time cuello de botella
4. Mayor id de proveedor

## Justificacion LLM
Los top 3 proveedores se envian a Ollama con el prompt de justificacion. Si Ollama recomienda un proveedor fuera del top 3, FastAPI usa el top 1.
