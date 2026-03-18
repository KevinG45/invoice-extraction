# Outputs Directory

All extraction outputs and data stores produced by the system.

## JSON Extraction Files

Located in `extractions/`. One JSON file per processed invoice, named `{source_stem}_{YYYYMMDD_HHMMSS}.json`.

### Top-Level Structure

| Field | Type | Description |
|-------|------|-------------|
| `invoice_number` | string\|null | Invoice identifier extracted from the document |
| `invoice_date` | string\|null | Invoice issue date |
| `due_date` | string\|null | Payment due date |
| `purchase_order_number` | string\|null | PO reference number |
| `vendor` | object | Seller information (see below) |
| `bill_to` | object | Buyer information (see below) |
| `ship_to` | object | Shipping destination (`name`, `address`) |
| `line_items` | array | Itemised charges (see below) |
| `subtotal` | number\|null | Sum before tax/discount |
| `discount` | number\|null | Discount amount |
| `tax_rate` | number\|null | Tax percentage |
| `tax_amount` | number\|null | Tax amount |
| `shipping` | number\|null | Shipping charges |
| `total_amount` | number\|null | Grand total |
| `amount_paid` | number\|null | Amount already paid |
| `amount_due` | number\|null | Remaining balance |
| `currency` | string\|null | Currency code (e.g. `INR`) |
| `payment_terms` | string\|null | Payment terms text |
| `payment_method` | string\|null | Payment method |
| `bank_details` | object\|null | Bank account info (`account`, `ifsc`, `name`, `branch`) |
| `notes` | string\|null | Additional notes |
| `validation` | object | Validation results (see below) |
| `metadata` | object | Processing metadata (see below) |

### Vendor Object

`name`, `address`, `email`, `phone`, `tax_id` (GSTIN), `website`.

### Bill-To Object

`name`, `address`, `email`.

### Line Item Object

| Field | Type | Description |
|-------|------|-------------|
| `line_number` | int | 1-based index |
| `description` | string | Item description |
| `quantity` | number | Quantity |
| `unit` | string\|null | Unit of measure |
| `unit_price` | number | Price per unit |
| `discount` | number\|null | Line discount |
| `tax_rate` | number\|null | Tax percentage |
| `total` | number | Line total |

### Validation Object

| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | True if no warnings |
| `warnings` | array[string] | List of validation issues |
| `math_checks` | object | `line_item_math` (per-line ok/note), `line_items_sum_to_subtotal`, `totals_consistent` |
| `line_item_count` | int | Number of line items found |

### Metadata Object

| Field | Type | Description |
|-------|------|-------------|
| `source_file` | string | Original filename |
| `source_path` | string | Path used during processing |
| `extraction_time` | string | ISO 8601 timestamp |
| `processing_seconds` | float | Wall-clock time for extraction |
| `pdf_type` | string | `digital`, `scanned`, or `image` |
| `page_count` | int | Number of pages |
| `ocr_engine` | string | OCR engine used (`paddleocr`, `tesseract`, `none`) |
| `tables_found` | int | Number of tables detected |
| `text_length` | int | Character count of extracted text |

---

## SQLite Database

Stored at `data/invoices.db`. Contains 3 tables:

### Table: `invoices`

Primary store for all extracted header fields. Key columns:

- `id` (INTEGER PK) -- auto-increment
- `source_file` (TEXT UNIQUE) -- original filename
- `source_path`, `processed_at`, `overall_confidence`, `validated`
- Invoice fields: `invoice_number`, `invoice_date`, `due_date`, `purchase_order_number`
- Vendor fields: `vendor_name`, `vendor_address`, `vendor_email`, `vendor_phone`, `vendor_tax_id`, `vendor_website`
- Bill-to fields: `bill_to_name`, `bill_to_address`, `bill_to_email`
- Ship-to fields: `ship_to_name`, `ship_to_address`
- Financial fields: `subtotal`, `discount`, `tax_rate`, `tax_amount`, `shipping`, `total_amount`, `amount_paid`, `amount_due`
- Other: `currency`, `payment_terms`, `payment_method`, `bank_details`, `notes`
- Processing metadata: `pdf_type`, `page_count`, `ocr_engine`, `tables_found`, `text_length`, `processing_seconds`

### Table: `line_items`

One row per line item, linked to `invoices.id`.

- `id` (INTEGER PK), `invoice_id` (FK -> invoices.id)
- `description`, `hsn_sac`, `quantity`, `unit_price`, `discount`, `tax_rate`, `tax_amount`, `total`

### Table: `validation_reports`

One row per invoice, linked to `invoices.id`.

- `id` (INTEGER PK), `invoice_id` (FK -> invoices.id)
- `passed` (BOOLEAN), `score` (REAL), `issues` (TEXT -- JSON string)

---

## ChromaDB Vector Store

Stored at `chroma_db/` (project root). Contains a persistent ChromaDB database with collection `invoices`. Uses `all-MiniLM-L6-v2` embeddings and cosine similarity. Each invoice is chunked into a header chunk and one chunk per line item for semantic retrieval.

## BM25 Keyword Index

Stored at `rag/bm25_index.pkl`. A pickled index built from all extraction JSONs for keyword-based retrieval. Rebuilt automatically on each new extraction or manually via `python run_bm25_index.py`.

---

## Known Limitations

### PaddleOCR Not Installed

Image table extraction currently uses a
regex-based fallback. For better accuracy on
complex invoice tables, install PaddleOCR:

```
pip install paddleocr>=2.7.0
```

This is a large install (approximately 2GB).
PDF extraction is unaffected and fully accurate.

**Additional requirement:** PaddleOCR depends on the `paddlepaddle` backend,
which currently has no wheel for Python 3.13 or later.
To use PPStructure table extraction you must run the project on **Python ≤3.12**
and install the paddle backend separately:

```
# CPU-only (recommended for most users):
pip install paddlepaddle

# GPU (CUDA 11.8):
pip install paddlepaddle-gpu==2.6.2.post118 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
```

Until the paddle backend supports Python 3.14+, image-type invoices are
processed using the regex fallback in `core/table_extractor.py`.
