# Modelo de datos

## suppliers
- id: integer, primary key
- company_name: varchar(255), required
- ruc: varchar(11), unico, 11 digitos
- email: varchar(255), unico, required
- phone: varchar(20), optional
- address: varchar(512), optional
- rating: numeric(4,2), default 5.00
- is_active: boolean, default true
- created_at: timestamptz
- updated_at: timestamptz

## products
- id: integer, primary key
- supplier_id: integer, FK suppliers.id, on delete cascade
- name: varchar(255), required
- description: varchar(2000), optional
- sku: varchar(64), required, unico por proveedor
- unit_price: numeric(12,2), non-negative
- currency: varchar(3), default PEN
- lead_time_days: integer, non-negative
- available_stock: integer, non-negative
- minimum_order_quantity: integer, non-negative
- is_active: boolean, default true
- created_at: timestamptz
- updated_at: timestamptz

## purchase_orders
- id: integer, primary key
- request_id: varchar(64), unico
- supplier_id: integer, FK suppliers.id, on delete restrict
- status: enum PENDING | APPROVED | SENT
- currency: varchar(3), default PEN
- total_amount: numeric(12,2), optional
- payload: jsonb, optional
- pdf_path: varchar(512), optional
- notes: varchar(4000), optional
- created_by: varchar(255), optional
- approved_by: varchar(255), optional
- created_at: timestamptz
- updated_at: timestamptz

## procurement_logs
- id: integer, primary key
- event_type: varchar(64), required
- event_source: varchar(128), optional
- message: varchar(2000), optional
- payload: jsonb, optional
- severity: enum DEBUG | INFO | WARNING | ERROR
- created_at: timestamptz
