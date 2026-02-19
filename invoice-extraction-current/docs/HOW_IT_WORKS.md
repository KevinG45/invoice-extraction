# Invoice Extraction System — How It Works

## What Does This Project Do?

This project **automatically reads invoices** (images or PDFs) and **pulls out key information** from them — like the invoice number, date, vendor name, total amount, and individual product/service line items.

Instead of a human manually reading each invoice and typing the data into a spreadsheet, this system does it automatically using AI models.

---

## What Information Does It Extract?

### Header Fields (top-level invoice info)
| Field | Example |
|---|---|
| Invoice Number | INV-2026-001 |
| Invoice Date | 2026-01-15 |
| Vendor/Seller Name | ABC Enterprises |
| Customer/Buyer Name | XYZ Corp |
| Total Amount | ₹15,000.00 |
| Payment Due Date | 2026-02-15 |

### Line Items (product/service rows in the invoice table)
| Field | Example |
|---|---|
| Item Code / SKU | WIDGET-001 |
| Description | Blue Widget |
| Quantity | 10 |
| Unit Price / Rate | ₹250.00 |
| Total | ₹2,500.00 |
| Tax | ₹450.00 |

---

## How Does It Work? (Step by Step)

The system works like a **pipeline** — the invoice passes through 5 stages, one after another:

```
Invoice Image/PDF
       │
       ▼
  ┌─────────────┐
  │  1. INPUT    │  Load the file, convert PDF pages to images
  │   HANDLER    │
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  2. OCR      │  Read all the text from the image using Tesseract
  │   ENGINE     │
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  3. AI MODEL │  Two AI models extract structured data:
  │  INFERENCE   │  • LayoutLM  → header fields
  │  (Hybrid)    │  • Donut     → line items (products, prices)
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  4. POST-    │  Clean up dates, fix amounts, validate data
  │  PROCESSOR   │
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  5. OUTPUT   │  Save results as JSON, CSV, Excel, or SQLite
  │   HANDLER    │
  └─────────────┘
```

---

## The 5 Stages Explained

### Stage 1: Input Handler
**What it does:** Takes your invoice file and prepares it for processing.

- If you give it a **PDF**, it converts each page into an image
- If you give it an **image** (JPG, PNG, etc.), it loads it directly
- It normalizes the image (fixes orientation, adjusts size/quality)
- It can process one file or an entire folder of invoices

**Files:** `src/input_handler/`

---

### Stage 2: OCR Engine (Tesseract)
**What it does:** Reads all the text from the invoice image.

- Uses **Tesseract OCR** — an open-source text recognition engine
- Extracts every word from the image along with its **position** (where it appears on the page)
- This position information (bounding boxes) is critical — it tells the AI model *where* each word is located on the invoice

**Why positions matter:** The AI model doesn't just read text — it understands the *layout*. It knows that text in the top-right is likely an invoice number, and text in a table row is a line item.

**Files:** `src/ocr_engine/`

---

### Stage 3: AI Model Inference (The Brain)
**What it does:** This is the core intelligence. Two AI models work together:

#### Model A: LayoutLM (`impira/layoutlm-document-qa`)
- **Purpose:** Extracts header fields (invoice number, date, names, total)
- **How it works:** Uses a **Question-Answering approach**
  - It asks: *"What is the invoice number?"* → The model looks at the text + layout and answers: *"INV-2026-001"*
  - It asks: *"What is the total amount?"* → The model answers: *"₹15,000.00"*
  - It does this for each of the 6 header fields
- **Why LayoutLM?** It understands document layout — it knows that text position matters (a number at the top-right of an invoice is likely the invoice number, not a phone number)

#### Model B: Donut (`naver-clova-ix/donut-base-finetuned-cord-v2`)
- **Purpose:** Extracts line items (product details, quantities, prices)
- **How it works:** It's an **OCR-free** model — it looks at the raw image directly (no Tesseract needed for this part)
  - It generates a structured output describing what it sees: item names, quantities, prices
  - It's specifically fine-tuned on receipt/invoice data (CORD dataset)
- **Why Donut?** It's excellent at reading tables and repetitive structured data like line items

#### Why Two Models? (Hybrid Approach)
Each model has strengths:
- LayoutLM is great at finding specific fields scattered across the page
- Donut is great at reading structured tables

Using both gives better results than either alone.

**Files:** `src/model_inference/`

---

### Stage 4: Post-Processor
**What it does:** Cleans up and validates the raw AI output.

The AI models give raw text answers. The post-processor:
- **Normalizes dates:** Converts "Jan 15, 2026" or "15/01/2026" → `2026-01-15` (standard format)
- **Normalizes amounts:** Converts "$1,500.00" or "₹ 1500" → `1500.00` (clean number)
- **Validates data:** Checks if the extracted invoice number looks real, if dates make sense
- **Cross-validates:** Compares the total amount from the header with the sum of line items — if they don't match, it flags a warning

**Files:** `src/postprocessor/`

---

### Stage 5: Output Handler
**What it does:** Saves the extracted data in your preferred format.

| Format | File | Use Case |
|---|---|---|
| **JSON** | `.json` | For APIs, software integration, easy to read |
| **CSV** | `.csv` | For spreadsheets, data analysis |
| **Excel** | `.xlsx` | For business users, has separate sheets for headers & line items |
| **SQLite** | `.db` | For database storage, querying |

**Files:** `src/output_handler/`

---

## Project Folder Structure

```
invoice-extraction-current/
├── main.py                  ← Entry point (run this file)
├── config/
│   └── settings.yaml        ← All configuration (model names, thresholds, etc.)
├── data/
│   └── input/INVOICES/      ← Put your invoices here (IMAGES/ and PDF/)
├── src/
│   ├── input_handler/       ← Stage 1: File loading
│   ├── ocr_engine/          ← Stage 2: Text recognition
│   ├── model_inference/     ← Stage 3: AI extraction
│   ├── postprocessor/       ← Stage 4: Data cleanup
│   ├── output_handler/      ← Stage 5: Save results
│   ├── evaluation/          ← Accuracy measurement tools
│   └── utils/               ← Logging, error handling, helpers
├── outputs/
│   └── extractions/         ← Results appear here
├── docs/                    ← Documentation
└── requirements.txt         ← Python packages needed
```

---

## How to Run It

```bash
# 1. Activate environment
conda activate invoice-extraction

# 2. Install dependencies (first time only)
pip install -r requirements.txt

# 3. Run on one image (JSON output only)
python main.py --input "data/input/INVOICES/IMAGES/invoice.jpg" --no-excel --no-database --debug

# 4. Run on all invoices in a folder
python main.py --input "data/input/INVOICES/IMAGES" --no-excel --no-database --debug
```

Results are saved in `outputs/extractions/`.

---

## Key Technologies Used

| Technology | What It Is | Role in This Project |
|---|---|---|
| **Python** | Programming language | Everything is written in Python |
| **Tesseract OCR** | Open-source text reader | Reads text + positions from images |
| **LayoutLM** | AI model by Microsoft/Impira | Extracts header fields using layout understanding |
| **Donut** | AI model by Naver (CLOVA) | Extracts line items from tables (OCR-free) |
| **Hugging Face Transformers** | AI model library | Loads and runs both AI models |
| **PyTorch** | Deep learning framework | Backend for running AI models |
| **Pandas** | Data library | Organizes data into tables for CSV/Excel |

---

## Example Output (JSON)

```json
{
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-01-15",
  "vendor_name": "ABC Enterprises",
  "customer_name": "XYZ Corp",
  "total_amount": "15000.00",
  "payment_due_date": "2026-02-15",
  "line_items": [
    {
      "description": "Blue Widget",
      "quantity": 10,
      "unit_price": 250.00,
      "total": 2500.00
    },
    {
      "description": "Red Gadget",
      "quantity": 5,
      "unit_price": 500.00,
      "total": 2500.00
    }
  ],
  "line_items_count": 2,
  "line_items_total": 5000.00
}
```

---

## In One Sentence

> This system takes an invoice image, reads it using OCR, uses two AI models to understand the document layout and extract both header information and product line items, cleans up the data, and saves it as structured JSON/CSV/Excel output.
