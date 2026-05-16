# Generacion PDF

## Servicio
El generador PDF usa WeasyPrint para crear una orden de compra desde HTML.

## Ubicacion de salida
- Ruta en contenedor: `/app/generated_pos`
- Ruta almacenada en DB: `generated_pos/<filename>`

## Nombre de archivo
```
PO_<request_id>_<YYYYMMDD_HHMMSS>.pdf
```

## Totales
El PDF incluye totales en PEN:
- Subtotal (suma de cantidad * unit_price)
- IGV 18%
- Total

## Campos incluidos
El documento incluye:
- Numero de OC (request_id)
- Fecha
- Nombre de proveedor, RUC y email
- Tabla de items con cantidad, precio unitario y subtotal
- Subtotal, IGV y total
