# Phase 2 — Database Architecture, Validation Layer, and Seed Data

## Objective
Your immediate priority is to implement the persistence and validation layer for the procurement system. This phase establishes the database foundation, ORM mappings, schema validation, migrations, and seed data required for future procurement workflows, scoring algorithms, PDF generation, and LLM-driven automation.

The implementation must follow clean architecture principles, maintain strict type safety, and be production-oriented from the start.

---

# Tasks

## 1. Create SQLAlchemy ORM Models

Translate the existing 3NF SQL schema into SQLAlchemy ORM models located inside:

backend/models/

All models must:

* Use SQLAlchemy 2.0 style typing (`Mapped`, `mapped_column`)
* Include proper relationships (`relationship`)
* Define indexes, constraints, and foreign keys
* Use UTC timestamps where appropriate
* Include `created_at` and `updated_at` fields when relevant
* Follow clean naming conventions
* Be production-ready and easily extendable

---

## Required Models

### `supplier.py`

Create a `Supplier` model containing:

* `id`
* `company_name`
* `ruc`
* `email`
* `phone`
* `address`
* `rating`
* `is_active`
* `created_at`
* `updated_at`

### Requirements

* `ruc` must:

  * contain exactly 11 digits
  * be unique
* `email` must be unique
* `rating` should support decimal values
* Add validation-ready structure for future compliance checks

---

### `product.py`

Create a `Product` model linked to suppliers.

Required fields:

* `id`
* `supplier_id`
* `name`
* `description`
* `sku`
* `unit_price`
* `currency`
* `lead_time_days`
* `available_stock`
* `minimum_order_quantity`
* `is_active`
* `created_at`
* `updated_at`

### Requirements

* Configure proper `ForeignKey` relationship with `Supplier`
* Add bidirectional relationships
* `currency` should default to `"PEN"`
* `unit_price` must support precise decimal values
* Ensure inventory-related fields are non-negative

---

### `purchase_order.py`

Create a `PurchaseOrder` model responsible for procurement lifecycle tracking.

Required fields:

* `id`
* `supplier_id`
* `status`
* `currency`
* `total_amount`
* `pdf_path`
* `notes`
* `created_by`
* `approved_by`
* `created_at`
* `updated_at`

### Requirements

* `status` should support:

  * `PENDING`
  * `APPROVED`
  * `SENT`
  * future extensibility
* `currency` must default to `"PEN"`
* Store the generated PDF file path
* Prepare the structure for future approval workflows

---

### `procurement_log.py`

Create a `ProcurementLog` model for audit trails and observability.

Required fields:

* `id`
* `event_type`
* `event_source`
* `message`
* `payload`
* `severity`
* `created_at`

### Requirements

This table should capture system activity such as:

* `EMAIL_RECEIVED`
* `LLM_REQUEST_STARTED`
* `LLM_FAILED`
* `PURCHASE_ORDER_CREATED`
* `PDF_GENERATED`

The `payload` field should support JSON storage for debugging and observability.

This model is critical for:

* traceability
* monitoring
* debugging AI workflows
* future analytics dashboards

---

# 2. Configure and Generate Alembic Migrations

After implementing the ORM models:

1. Import all models into:

```plaintext
backend/alembic/env.py
```

2. Configure metadata discovery properly.

3. Generate the initial migration.

4. Verify:

   * constraints
   * foreign keys
   * indexes
   * enum generation
   * timestamp defaults

5. Apply migrations against the development database.

### Deliverables

* Initial Alembic migration file
* Verified schema generation
* Clean migration history

---

# 3. Build Pydantic Validation Schemas

Create validation schemas inside:

```plaintext
backend/schemas/
```

Examples:

* `procurement_request.py`
* `purchase_order.py`
* `supplier.py`
* `product.py`

---

## Validation Requirements

The validation layer is mandatory because future LLM-generated outputs must never directly reach the database without schema validation.

Implement:

* strict typing
* enum validation
* decimal validation
* field constraints
* email validation
* length validation
* nullable handling
* ORM compatibility (`from_attributes=True` if using Pydantic v2)

### Important

Design schemas with future AI integration in mind:

* defensive validation
* predictable serialization
* structured error handling

---

# 4. Seed the Database

Create:

```plaintext
db/seed.py
```

This script must populate the database with realistic dummy data.

---

## Seed Requirements

Insert at least:

* 10 suppliers
* multiple products per supplier

Each supplier should contain realistic:

* company names
* RUC values
* pricing ranges
* ratings
* stock levels
* lead times

The generated dataset will later be used to test:

* supplier ranking
* Weighted Linear Combination (WLC) scoring
* procurement recommendations
* approval flows
* LLM-assisted purchasing logic

---

# Technical Expectations

## Code Quality

The implementation must follow:

* clean architecture
* separation of concerns
* modularity
* scalability
* production-grade standards

Avoid:

* monolithic models
* duplicated validation logic
* hardcoded values
* weak typing

---

# Expected Deliverables

By the end of this phase, the project must include:

* SQLAlchemy ORM models
* relational mappings
* Alembic migrations
* validated Pydantic schemas
* database seed script
* realistic procurement test data

The system should be fully prepared for:

* API endpoint implementation
* procurement workflows
* supplier scoring algorithms
* AI-assisted automation
* PDF generation
* audit logging

```
```
