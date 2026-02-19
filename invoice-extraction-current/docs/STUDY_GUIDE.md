# Invoice Extraction System — Complete Study Guide

> **Version:** 3.0.0 (Baseline)  
> **Date:** 2026-02-19  
> **Audience:** Students, researchers, and engineers new to document AI  
> **Prerequisite Knowledge:** Basic Python programming  

---

## Table of Contents

1. [What is Invoice Extraction?](#1-what-is-invoice-extraction)
2. [Key Terms & Glossary](#2-key-terms--glossary)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [The Complete Pipeline — Step by Step](#4-the-complete-pipeline--step-by-step)
   - 4.1 [Document Loading](#41-document-loading)
   - 4.2 [Text Extraction](#42-text-extraction)
   - 4.3 [Header Field Extraction](#43-header-field-extraction)
   - 4.4 [Line Item / Table Extraction](#44-line-item--table-extraction)
   - 4.5 [Post-Processing & Validation](#45-post-processing--validation)
   - 4.6 [Export](#46-export)
5. [Data Structures & How Data Flows](#5-data-structures--how-data-flows)
6. [Technologies Used](#6-technologies-used)
7. [Indian GST Invoice Specifics](#7-indian-gst-invoice-specifics)
8. [Project Code Map](#8-project-code-map)
9. [How to Run the System](#9-how-to-run-the-system)
10. [Bugs Found & Lessons Learned](#10-bugs-found--lessons-learned)
11. [Next Phase: RAG-Enhanced Extraction](#11-next-phase-rag-enhanced-extraction)
12. [Research References & Further Reading](#12-research-references--further-reading)

---

## 1. What is Invoice Extraction?

**Invoice extraction** is the process of automatically reading an invoice document (PDF or image) and pulling out structured data — like the invoice number, date, vendor name, amounts, and the table of purchased items.

### Why does this matter?

Businesses receive thousands of invoices. Manually typing data from each one into a spreadsheet or accounting system is:
- **Slow** — a human might process 20-30 invoices per hour
- **Error-prone** — typos, missed fields, wrong numbers
- **Expensive** — requires dedicated data entry staff

An automated system can process hundreds of invoices per minute with consistent accuracy.

### What we extract

From every invoice, we extract **two categories** of information:

```
┌─────────────────────────────────────────────────────────────┐
│                    INVOICE DATA                              │
│                                                              │
│  HEADER FIELDS (14 fields):                                  │
│  ┌─────────────────┬──────────────────────────────────────┐  │
│  │ invoice_number   │ "INV-2026-001"                      │  │
│  │ invoice_date     │ "2026-01-15"                        │  │
│  │ due_date         │ "2026-02-15"                        │  │
│  │ vendor_name      │ "ABC Supplies Ltd."                 │  │
│  │ vendor_address   │ "123 Main St, Mumbai"               │  │
│  │ vendor_email     │ "sales@abc.com"                     │  │
│  │ vendor_phone     │ "+91 98765 43210"                   │  │
│  │ vendor_gstin     │ "27AABCU9603R1ZM"                   │  │
│  │ customer_name    │ "XYZ Corporation"                   │  │
│  │ customer_address │ "456 Oak Ave, Delhi"                │  │
│  │ customer_gstin   │ "07AAACC1206D1ZM"                   │  │
│  │ subtotal         │ 10000.00                            │  │
│  │ tax_amount       │ 1800.00                             │  │
│  │ total_amount     │ 11800.00                            │  │
│  └─────────────────┴──────────────────────────────────────┘  │
│                                                              │
│  LINE ITEMS (variable count):                                │
│  ┌────┬──────────────┬─────┬──────────┬──────────┐          │
│  │ #  │ Description  │ Qty │ Price    │ Total    │          │
│  ├────┼──────────────┼─────┼──────────┼──────────┤          │
│  │ 1  │ Widget A     │ 10  │ 500.00   │ 5000.00  │          │
│  │ 2  │ Widget B     │ 5   │ 1000.00  │ 5000.00  │          │
│  └────┴──────────────┴─────┴──────────┴──────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Key Terms & Glossary

Every technical term used in this project is explained here. Refer back to this section as you read the guide.

| Term | Definition |
|------|-----------|
| **OCR** | **Optical Character Recognition** — Technology that converts images of text into machine-readable text. Like teaching a computer to "read" a photograph of a page. |
| **Digital PDF** | A PDF where the text is stored as selectable characters (you can copy-paste from it). Created by software like Word or Excel. |
| **Scanned PDF** | A PDF that is just a picture of a document (you cannot select text). Created by scanning a paper document. |
| **Tesseract** | A free, open-source OCR engine originally developed by HP, now maintained by Google. Converts images to text. |
| **pdfplumber** | A Python library that reads text directly from digital PDFs. Much more accurate than OCR because it reads the actual text data, not pixels. |
| **PyMuPDF (fitz)** | A Python library for rendering PDF pages as images. Used when we need to convert a PDF page to a picture (for OCR or model input). |
| **LayoutLMv3** | A machine learning model by Microsoft that understands both the text AND the visual layout of documents. It can answer questions like "What is the invoice number?" by looking at both the words and where they are on the page. |
| **Regex** | **Regular Expression** — A pattern-matching language for text. For example, `\d{2}/\d{2}/\d{4}` matches dates like "15/01/2026". |
| **Confidence Score** | A number from 0 to 100 that indicates how certain we are about an extracted value. 95% = very confident, 40% = uncertain. |
| **GSTIN** | **GST Identification Number** — A 15-character unique ID assigned to businesses registered under India's GST (Goods and Services Tax) system. Format: `27AABCU9603R1ZM`. |
| **HSN/SAC Code** | **Harmonized System of Nomenclature / Service Accounting Code** — Codes used in Indian GST to classify goods (HSN) and services (SAC). Example: HSN 8471 = Computers. |
| **CGST / SGST / IGST** | Types of GST tax: **Central GST** (goes to central government), **State GST** (goes to state government), **Integrated GST** (for inter-state transactions, replaces CGST+SGST). |
| **Cross-validation** | Checking extracted data for internal consistency. Example: if subtotal is ₹1000 and tax is ₹180, the total should be ₹1180. If it's not, something was extracted wrong. |
| **Pipeline** | A series of processing steps that data flows through sequentially. Like an assembly line — each stage transforms the data and passes it to the next. |
| **Binarization** | Converting a grayscale image to pure black and white. Makes text clearer for OCR. |
| **Adaptive Threshold** | A binarization method that adjusts the black/white cutoff locally (different for each region of the image), handling uneven lighting. |
| **DPI** | **Dots Per Inch** — Resolution of an image. 300 DPI is standard for OCR. Higher = clearer but larger file. |
| **PIL / Pillow** | **Python Imaging Library** — Python library for opening, manipulating, and saving images. |
| **Dataclass** | A Python feature (@dataclass decorator) that automatically generates `__init__`, `__repr__`, etc. for classes that mainly hold data. |
| **RAG** | **Retrieval-Augmented Generation** — An AI technique that combines information retrieval (searching a knowledge base) with text generation. Planned for Phase 2. |
| **LLM** | **Large Language Model** — AI models like GPT-4, Claude, Gemini that understand and generate text. Some can also understand images (multimodal). |

---

## 3. System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BASELINE EXTRACTION PIPELINE v3.0                 │
│                                                                     │
│   INPUT                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│   │ PDF Files │  │ JPG/PNG  │  │ TIFF/BMP │                        │
│   └─────┬────┘  └─────┬────┘  └─────┬────┘                        │
│         └──────────────┼─────────────┘                              │
│                        ▼                                            │
│   ┌────────────────────────────────────┐                            │
│   │      STEP 1: DOCUMENT LOADER       │                            │
│   │  • Detect file type (PDF/Image)    │                            │
│   │  • Classify: digital or scanned    │                            │
│   │  • Convert pages to images         │                            │
│   └────────────────┬───────────────────┘                            │
│                    │                                                │
│         ┌──────────┴──────────┐                                     │
│         ▼                     ▼                                     │
│   ┌───────────────┐   ┌──────────────┐                              │
│   │ DIGITAL PDF   │   │ IMAGE/SCAN   │                              │
│   │  pdfplumber   │   │  Tesseract   │                              │
│   │  (100% acc.)  │   │  OCR Engine  │                              │
│   └───────┬───────┘   └──────┬───────┘                              │
│           └─────────┬────────┘                                      │
│                     ▼                                               │
│   ┌────────────────────────────────────┐                            │
│   │      STEP 3: FIELD EXTRACTOR       │                            │
│   │  • Regex patterns (14 fields)      │                            │
│   │  • LayoutLMv3 Document QA          │                            │
│   │  • Merge: higher confidence wins   │                            │
│   └────────────────┬───────────────────┘                            │
│                    │                                                │
│   ┌────────────────▼───────────────────┐                            │
│   │      STEP 4: TABLE EXTRACTOR       │                            │
│   │  • pdfplumber tables (digital PDF) │                            │
│   │  • Regex row parsing (OCR text)    │                            │
│   │  • Column mapping + validation     │                            │
│   └────────────────┬───────────────────┘                            │
│                    │                                                │
│   ┌────────────────▼───────────────────┐                            │
│   │      STEP 5: POST-PROCESSOR        │                            │
│   │  • Normalize dates → YYYY-MM-DD    │                            │
│   │  • Normalize amounts → 2 decimals  │                            │
│   │  • Cross-validate totals           │                            │
│   │  • Adjust confidence scores        │                            │
│   └────────────────┬───────────────────┘                            │
│                    │                                                │
│   ┌────────────────▼───────────────────┐                            │
│   │      STEP 6: EXPORT                │                            │
│   │  • JSON  (full metadata)           │                            │
│   │  • Excel (Headers + Line Items)    │                            │
│   │  • CSV   (flat tables)             │                            │
│   └────────────────────────────────────┘                            │
│                                                                     │
│   OUTPUT                                                            │
│   ┌────────────┐  ┌────────────┐  ┌──────────────┐                 │
│   │ .json      │  │ .xlsx      │  │ .csv (×2)    │                 │
│   │ Full data  │  │ 2 sheets   │  │ headers.csv  │                 │
│   │ + metadata │  │ formatted  │  │ items.csv    │                 │
│   └────────────┘  └────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

We chose a **modular pipeline architecture** where each step is an independent module (Python file). This gives us:

1. **Testability** — Each module can be tested independently
2. **Flexibility** — Swap OCR engines, add new extractors, change export formats
3. **Debuggability** — If results are wrong, we can check each step separately
4. **Extensibility** — Easy to add new steps (like RAG validation in Phase 2)

---

## 4. The Complete Pipeline — Step by Step

### 4.1 Document Loading

**File:** `src/baseline/document_loader.py`

**What it does:** Opens invoice files and figures out what kind of document they are.

**Why it matters:** Different document types need different extraction strategies. A digital PDF has perfect text we can read directly. A scanned image needs OCR.

#### Document Type Detection (flowchart)

```
                    ┌──────────────┐
                    │  Input File  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Extension?  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌─────────┐  ┌─────────┐
         │  .pdf  │  │ .jpg    │  │ .tiff   │
         │        │  │ .png    │  │ .bmp    │
         └───┬────┘  └────┬────┘  └────┬────┘
             │             │            │
    ┌────────▼────────┐    │            │
    │ Open with        │    │            │
    │ pdfplumber,      │    │            │
    │ extract text     │    │            │
    │ from page 1      │    │            │
    └────────┬────────┘    │            │
             │              │            │
    ┌────────▼────────┐    │            │
    │ Text > 50 chars? │    │            │
    └────────┬────────┘    │            │
        YES  │  NO         │            │
     ┌───────┘ └───────┐   │            │
     ▼                  ▼   ▼            ▼
┌──────────┐     ┌──────────────────────────┐
│ DIGITAL  │     │  SCANNED / IMAGE         │
│ PDF      │     │  → needs OCR             │
│ (perfect │     │  → convert to images     │
│  text)   │     │    at 300 DPI            │
└──────────┘     └──────────────────────────┘
```

#### Key Concepts

**DPI (Dots Per Inch):** When converting a PDF page to an image, we render at 300 DPI. This means every inch of the page becomes 300 pixels. Higher DPI gives clearer text for OCR but creates larger images. 300 DPI is the sweet spot.

**RGB Conversion:** Images come in many formats (RGBA with transparency, grayscale, CMYK for commercial printing). We convert everything to RGB (Red-Green-Blue, standard color) for consistency.

---

### 4.2 Text Extraction

**File:** `src/baseline/text_extractor.py`

**What it does:** Converts documents into machine-readable text.

#### Track A: Digital PDF → pdfplumber

```
  Digital PDF file
       │
       ▼
  ┌─────────────────┐
  │  pdfplumber      │  ← Python library
  │  .extract_text() │     Reads Unicode text directly from PDF
  │  .extract_words()│     Also gives position of each word
  │  .extract_tables()│    Detects and extracts table structures
  └────────┬─────────┘
           │
           ▼
  ┌─────────────────────────────────────┐
  │  Result:                            │
  │  • full_text: "Invoice No: INV..."  │  ← Complete text
  │  • text_blocks: [{word, position}]  │  ← Each word + location
  │  • tables: [[[cell, cell], ...]]    │  ← Detected tables
  │  • confidence: 99%                  │  ← Perfect accuracy
  └─────────────────────────────────────┘
```

**Why pdfplumber is so accurate:** Digital PDFs store text as Unicode characters with exact positions. pdfplumber simply reads these characters — no guessing needed. It's like reading a Word document.

#### Track B: Image / Scanned PDF → Tesseract OCR

```
  Image or scanned page
       │
       ▼
  ┌──────────────────────────────────────┐
  │        IMAGE PREPROCESSING           │
  │                                      │
  │  1. Upscale if too small (< 1000px)  │
  │     Why: OCR needs large characters  │
  │                                      │
  │  2. Enhance contrast (×1.5)          │
  │     Why: Make text darker, bg lighter│
  │                                      │
  │  3. Sharpen (×1.5)                   │
  │     Why: Clearer character edges     │
  │                                      │
  │  4. Median denoise (3×3)             │
  │     Why: Remove speckles/noise       │
  │                                      │
  │  5. Adaptive binarization            │
  │     Why: Convert to black & white    │
  │     using local thresholds           │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │         TESSERACT OCR                │
  │                                      │
  │  Input: preprocessed grayscale image │
  │  Mode: PSM 6 (uniform text block)   │
  │  Language: English (eng)             │
  │                                      │
  │  Process:                            │
  │  1. Detect text regions              │
  │  2. Segment into lines and words     │
  │  3. Recognize each character         │
  │  4. Build words with confidence      │
  │  5. Return text + bounding boxes     │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌─────────────────────────────────────┐
  │  Result:                            │
  │  • full_text: "Invioce No: INV..." │  ← May have OCR errors!
  │  • text_blocks: [{word, conf, pos}] │  ← Confidence per word
  │  • tables: []                       │  ← No table detection
  │  • confidence: 70-90%               │  ← Varies by quality
  └─────────────────────────────────────┘
```

#### What is Adaptive Binarization?

Regular binarization uses one threshold for the entire image: every pixel above the threshold becomes white, below becomes black. This fails when lighting is uneven (e.g., shadow on one side).

**Adaptive binarization** calculates a different threshold for each pixel based on its local neighborhood (25×25 pixel window). This handles:
- Shadows across the document
- Uneven scanner lighting
- Gradient backgrounds

```
  Before adaptive binarization:       After:
  ┌────────────────────────┐          ┌────────────────────────┐
  │░░░░ Invoice No: 001 ░░│          │     Invoice No: 001    │
  │░░░░ Date: 15/01 ░░░░░░│    →     │     Date: 15/01        │
  │▓▓▓▓ Total: $500 ▓▓▓▓▓▓│          │     Total: $500        │
  │▓▓▓▓              ▓▓▓▓▓│          │                        │
  └────────────────────────┘          └────────────────────────┘
   (shadow on left side)              (clean black & white)
```

---

### 4.3 Header Field Extraction

**File:** `src/baseline/field_extractor.py`

**What it does:** Finds the 14 header fields (invoice number, dates, names, amounts) in the extracted text.

#### Two-Strategy Approach

```
  ┌─────────────────────────┐
  │   Extracted Text         │
  │   "Invoice No: INV-001"  │
  │   "Date: 15/01/2026"     │
  │   "Total: ₹11,800.00"   │
  └───────────┬─────────────┘
              │
    ┌─────────┴──────────┐
    ▼                    ▼
┌───────────────┐  ┌───────────────┐
│ STRATEGY 1:   │  │ STRATEGY 2:   │
│ REGEX         │  │ LAYOUTLM QA   │
│               │  │               │
│ Fast, precise │  │ Slower, smart │
│ Pattern-based │  │ ML-based      │
│ No ML needed  │  │ ~400MB model  │
│               │  │               │
│ Best for:     │  │ Best for:     │
│ • Numbers     │  │ • Names       │
│ • Dates       │  │ • Addresses   │
│ • Amounts     │  │ • Ambiguous   │
│ • GSTIN       │  │   fields      │
└───────┬───────┘  └───────┬───────┘
        │                  │
        └─────────┬────────┘
                  ▼
         ┌────────────────┐
         │    MERGE        │
         │                 │
         │ For each field: │
         │ Keep the result │
         │ with HIGHER     │
         │ confidence      │
         └────────────────┘
```

#### How Regex Extraction Works (Example)

For the field "invoice_number", we try these patterns in order:

```python
# Pattern 1: "Invoice No" / "Invoice Number" / "Invoice #"
r"(?:invoice\s*(?:no\.?|number|#))\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})"

# Let's break this down:
#
#  (?:invoice\s*(?:no\.?|number|#))   ← Match "Invoice No", "Invoice Number", "Invoice #"
#     (?:...)  = non-capturing group (match but don't save)
#     \s*      = any whitespace (spaces, tabs)
#     \.?      = optional period
#     |        = OR
#
#  \s*[:\-]?\s*    ← Match optional ":" or "-" with spaces
#
#  ([A-Za-z0-9][\w\-/\.#]{2,30})   ← CAPTURE the actual invoice number
#     (...)    = capturing group — this is what we extract
#     [A-Za-z0-9] = starts with letter or digit
#     [\w\-/\.#]{2,30} = followed by 2-30 word chars, dashes, slashes, dots, hashes
```

**Example matches:**
- `"Invoice No: INV-2026-001"` → captures `"INV-2026-001"`
- `"Invoice Number : GST/24/001"` → captures `"GST/24/001"`
- `"Invoice # 12345"` → captures `"12345"`

#### How LayoutLM Document QA Works

LayoutLM is a neural network that takes a **document image** and a **question**, then finds the answer in the document.

```
  INPUT:                           OUTPUT:
  ┌──────────────────────┐        ┌─────────────────────┐
  │ Image: [invoice.jpg] │   →    │ Answer: "INV-001"   │
  │ Question: "What is   │        │ Score: 0.95         │
  │  the invoice number?"│        └─────────────────────┘
  └──────────────────────┘

  How it works internally:
  1. The model "sees" the image (like looking at the invoice)
  2. It reads the text AND notes WHERE text is positioned
  3. It understands that "Invoice No:" is a LABEL
  4. It knows the VALUE is usually right after the label
  5. It extracts "INV-001" as the answer
  6. It gives a confidence score (0.95 = 95% sure)
```

**Why both strategies?** Regex is extremely fast and accurate for structured fields (numbers, dates) but fails on free-text fields. LayoutLM understands context but is slower (~500ms per question) and requires a ~400MB model download.

---

### 4.4 Line Item / Table Extraction

**File:** `src/baseline/table_extractor.py`

**What it does:** Extracts the product/service rows from the invoice table.

#### Strategy 1: pdfplumber Table Detection (Digital PDFs)

pdfplumber can detect tables by finding ruling lines and cell boundaries:

```
  PDF with table:                      pdfplumber output:
  ┌────┬──────────┬─────┬────────┐    [
  │ S# │ Item     │ Qty │ Total  │      ["S#", "Item", "Qty", "Total"],     ← header row
  ├────┼──────────┼─────┼────────┤      ["1", "Widget A", "10", "5000"],     ← data row
  │ 1  │ Widget A │ 10  │ 5000   │      ["2", "Widget B", "5",  "1500"],     ← data row
  │ 2  │ Widget B │ 5   │ 1500   │    ]
  └────┴──────────┴─────┴────────┘
```

The extractor then:
1. **Finds the header row** — matches column names against known keywords
2. **Maps columns** — `"Item"` → description, `"Qty"` → quantity, `"Total"` → line_total
3. **Parses data rows** — converts each row into a `LineItem` object
4. **Skips summary rows** — ignores rows containing "Total", "Subtotal", "Tax"

#### Strategy 2: Text-Based Parsing (OCR Output)

When we only have raw text (no table structure), we use heuristics:

```
  OCR text:
  "S.No  Description       Qty    Rate    Amount"
  "1     Widget A          10     500     5000"
  "2     Widget B          5      300     1500"
  "Total                                  6500"

  Steps:
  1. Find header row (line with 3+ column keywords)  → Line 1
  2. Find end of table (line starting with "Total")  → Line 4
  3. Parse rows 2-3:
     - Split by multiple spaces
     - Identify text parts (description) vs numbers
     - Last number = amount, first small number = quantity
  4. Skip the "Total" row (it's a summary, not a line item)
```

#### Column Identification

The extractor knows 10 categories of column names:

| Category | Keywords it recognizes |
|----------|----------------------|
| serial | s.no, sr.no, sl, #, no., line |
| item_code | item code, sku, part no, code |
| description | description, particulars, item, product, goods |
| hsn_sac | hsn, sac, hsn/sac, tariff |
| quantity | qty, quantity, nos, pcs, pieces |
| unit_price | rate, price, unit price, mrp, per unit |
| discount | discount, disc, rebate |
| tax_rate | gst, gst%, tax rate, cgst, sgst, vat |
| tax_amount | tax amount, tax amt, gst amt |
| line_total | amount, total, net amount, value, taxable value |

---

### 4.5 Post-Processing & Validation

**File:** `src/baseline/postprocessor.py`

**What it does:** Cleans up extracted data and checks for internal consistency.

#### Post-Processing Steps

```
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 1: DATE NORMALIZATION                              │
  │                                                          │
  │  "15/01/2026"    → "2026-01-15"  (DD/MM/YYYY → ISO)    │
  │  "Jan 15, 2026"  → "2026-01-15"  (Month name → ISO)    │
  │  "15-Jan-26"     → "2026-01-15"  (2-digit year → 4)    │
  │                                                          │
  │  Priority: DD/MM/YYYY (Indian format) over MM/DD/YYYY   │
  └─────────────────────────────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │  STEP 2: AMOUNT NORMALIZATION                            │
  │                                                          │
  │  "₹1,234.56"       → 1234.56  (remove symbol + commas) │
  │  "Rs. 12,34,567.89"→ 1234567.89  (Indian numbering!)   │
  │  All amounts: 2 decimal places                           │
  └─────────────────────────────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │  STEP 3: TEXT CLEANUP                                    │
  │                                                          │
  │  "  ABC   SUPPLIES   LTD  " → "Abc Supplies Ltd"       │
  │  Names: Title Case (unless ALL CAPS branding)            │
  │  Emails: lowercase                                       │
  │  Remove control characters, normalize spaces             │
  └─────────────────────────────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │  STEP 4: CROSS-VALIDATION                                │
  │                                                          │
  │  Check 1: subtotal + tax ≈ total  (within 5%)           │
  │  Check 2: sum(line_totals) ≈ subtotal  (within 10%)     │
  │  Check 3: qty × price ≈ line_total  (per item)          │
  │  Check 4: due_date ≥ invoice_date                        │
  │  Check 5: GSTIN format valid (15 chars, state code 1-37)│
  │                                                          │
  │  Each check returns: PASS / FAIL / SKIP                  │
  └─────────────────────────────────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────────┐
  │  STEP 5: CONFIDENCE ADJUSTMENT                           │
  │                                                          │
  │  If total_consistency PASSES:                            │
  │    → Boost amount field confidence by +10 points         │
  │  If total_consistency FAILS:                             │
  │    → Reduce amount field confidence by -15 points        │
  │    → Mark amounts as "uncertain"                         │
  │                                                          │
  │  Same for line item math checks                          │
  └─────────────────────────────────────────────────────────┘
```

#### Why Cross-Validation is Powerful

Imagine OCR misreads "5000" as "8000":

```
Without cross-validation:             With cross-validation:
  Line 1: qty=10, price=500           Line 1: qty=10, price=500
  Line 1: total=8000  ✓ (accepted)    Line 1: total=8000  ✗ FAIL!
                                         10 × 500 = 5000 ≠ 8000
                                         → Confidence reduced
                                         → Flagged for review
```

---

### 4.6 Export

**File:** `src/baseline/export.py`

**What it does:** Saves results in three formats.

| Format | Use Case | What's Included |
|--------|----------|-----------------|
| **JSON** | Machine processing, API responses | Everything: headers, line items, metadata, confidence scores, validation results |
| **Excel** | Human review, manual verification | Two sheets: "Headers" (one row per invoice) and "Line Items" (one row per item). Color-coded headers. |
| **CSV** | Import into other tools, data analysis | Two files: `headers.csv` and `items.csv`. Flat format, easy to load into pandas/Excel. |

---

## 5. Data Structures & How Data Flows

**File:** `src/baseline/result.py`

### The Core Objects

```
┌─────────────────────────────────────────────────────────────┐
│                     InvoiceResult                            │
│  (Complete extraction for ONE invoice)                       │
│                                                              │
│  ┌──────────── headers ─────────────┐                       │
│  │  Dict[str, HeaderField]          │                       │
│  │                                  │                       │
│  │  "invoice_number" → HeaderField( │                       │
│  │      value="INV-001",            │                       │
│  │      confidence=92.0,            │                       │
│  │      source="regex",             │                       │
│  │      uncertain=False             │                       │
│  │  )                               │                       │
│  │  "total_amount" → HeaderField(   │                       │
│  │      value="11800.00",           │                       │
│  │      confidence=85.0,            │                       │
│  │      source="layoutlm",          │                       │
│  │      uncertain=False             │                       │
│  │  )                               │                       │
│  │  ... (14 fields total)           │                       │
│  └──────────────────────────────────┘                       │
│                                                              │
│  ┌──────────── line_items ──────────┐                       │
│  │  List[LineItem]                  │                       │
│  │                                  │                       │
│  │  LineItem(                       │                       │
│  │    line_number=1,                │                       │
│  │    description="Widget A",       │                       │
│  │    quantity=10.0,                │                       │
│  │    unit_price=500.0,             │                       │
│  │    line_total=5000.0,            │                       │
│  │    confidence=85.0               │                       │
│  │  )                               │                       │
│  │  ... (variable count)            │                       │
│  └──────────────────────────────────┘                       │
│                                                              │
│  ┌──────────── metadata ────────────┐                       │
│  │  ExtractionMetadata(             │                       │
│  │    source_file="GST001.pdf",     │                       │
│  │    document_type="digital_pdf",  │                       │
│  │    page_count=1,                 │                       │
│  │    text_extraction_method=       │                       │
│  │      "pdfplumber",               │                       │
│  │    total_extraction_time_ms=450  │                       │
│  │  )                               │                       │
│  └──────────────────────────────────┘                       │
│                                                              │
│  ┌──────────── validation ──────────┐                       │
│  │  validation_results: [           │                       │
│  │    {"check": "total_consistency",│                       │
│  │     "status": "PASS",            │                       │
│  │     "message": "10000 + 1800 =   │                       │
│  │       11800 ≈ 11800"}            │                       │
│  │  ]                               │                       │
│  │  validation_passed: True         │                       │
│  │  overall_confidence: 87.5        │                       │
│  └──────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Through the Pipeline

```
Step 1 (Loader)    →  LoadedDocument (images, type, pdfplumber_doc)
Step 2 (Text)      →  ExtractedText  (full_text, text_blocks, tables)
Step 3 (Fields)    →  InvoiceResult.headers gets populated
Step 4 (Table)     →  InvoiceResult.line_items gets populated
Step 5 (PostProc)  →  InvoiceResult.headers cleaned, validation_results added
Step 6 (Export)    →  InvoiceResult.to_dict() → JSON/Excel/CSV files
```

The `InvoiceResult` object is created at the start and **passed through every step**. Each step adds or modifies data in place. This avoids copying large data structures.

### The set_header() Smart Update

```python
result.set_header("total_amount", value="11800", confidence=80, source="regex")
# → Stored: total_amount = "11800" (confidence 80)

result.set_header("total_amount", value="11800.00", confidence=92, source="layoutlm")
# → UPDATED: total_amount = "11800.00" (confidence 92 > 80)

result.set_header("total_amount", value="12000", confidence=60, source="regex")
# → IGNORED: confidence 60 < 92 (existing is better)
```

---

## 6. Technologies Used

### Core Libraries

| Library | Version | Purpose | Why We Chose It |
|---------|---------|---------|----------------|
| **pdfplumber** | 0.11+ | Read text from digital PDFs | Most accurate PDF text library for Python. Better table detection than PyPDF2. |
| **PyMuPDF (fitz)** | 1.24+ | Convert PDF pages to images | Fastest PDF renderer. No external dependencies (unlike pdf2image which needs Poppler). |
| **pytesseract** | 0.3+ | OCR for images | Free, open-source, supports 100+ languages. Tesseract 5.x has LSTM-based recognition. |
| **Pillow (PIL)** | 10+ | Image processing | Standard Python imaging library. Used for resizing, enhancing, converting. |
| **transformers** | 4.40+ | LayoutLMv3 model | HuggingFace library for ML models. Easy to load pre-trained models. |
| **openpyxl** | 3.1+ | Excel file creation | Creates .xlsx files with formatting, multiple sheets, styling. |
| **numpy** | 1.24+ | Numeric processing | Used for adaptive binarization (matrix operations on image pixels). |

### ML Models

| Model | Size | Speed | Purpose |
|-------|------|-------|---------|
| **impira/layoutlm-document-qa** | ~400MB | ~500ms/question | Document QA — asks questions about document images |

### External Tools

| Tool | Purpose |
|------|---------|
| **Tesseract OCR** | Must be installed on the system (not just the Python package). Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki). |

---

## 7. Indian GST Invoice Specifics

Our system is optimized for **Indian GST invoices**, which have specific features:

### GSTIN (GST Identification Number)

```
  Format: 27AABCU9603R1ZM  (15 characters)
           ││     │       │
           ││     │       └── Check digit (alphanumeric)
           ││     │           Z is always literal 'Z'
           ││     └────────── Entity number (1-9, A-Z)
           │└──────────────── PAN (10 characters)
           └───────────────── State code (01-37)

  State codes: 01=Jammu & Kashmir, 06=Haryana, 07=Delhi,
               27=Maharashtra, 29=Karnataka, 33=Tamil Nadu

  Regex: \d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9]
```

### GST Tax Structure

```
  INTRA-STATE (within same state):
    CGST (Central GST) = 9%     ← Goes to Central Government
    SGST (State GST)   = 9%     ← Goes to State Government
    Total GST          = 18%

  INTER-STATE (between different states):
    IGST (Integrated GST) = 18%  ← Split between Central & State later

  Our system:
    1. Finds CGST + SGST amounts in the invoice
    2. Sums them: total_tax = CGST + SGST
    3. Stores as the "tax_amount" field
```

### Indian Date Format

```
  India uses DD/MM/YYYY (day first): 15/01/2026 = January 15
  USA uses MM/DD/YYYY (month first): 01/15/2026 = January 15

  Ambiguous: "05/06/2026" — is it May 6th or June 5th?

  Our system defaults to DD/MM/YYYY (Indian) with a config option
  to switch to MM/DD/YYYY for non-Indian invoices.
```

### Indian Number Format

```
  Western: 1,234,567.89  (groups of three digits)
  Indian:  12,34,567.89  (groups of two digits after the thousands)

  Both are handled by our amount normalizer:
    "₹12,34,567.89" → 1234567.89
    "Rs. 1,234.56"  → 1234.56
```

---

## 8. Project Code Map

### File Structure

```
invoice-extraction-current/
├── run_baseline.py          ← CLI entry point (run this!)
├── CHECKLIST.md             ← Build checklist with 10 phases
├── requirements.txt         ← Python dependencies
│
├── src/baseline/            ← THE BASELINE PIPELINE (our code)
│   ├── __init__.py          ← Package init, exports key classes
│   ├── result.py            ← Data structures (InvoiceResult, HeaderField, LineItem)
│   ├── document_loader.py   ← Load PDFs and images, detect type
│   ├── text_extractor.py    ← pdfplumber + Tesseract OCR
│   ├── field_extractor.py   ← Regex + LayoutLM for header fields
│   ├── table_extractor.py   ← Table detection + line item parsing
│   ├── postprocessor.py     ← Normalize, validate, adjust confidence
│   ├── export.py            ← JSON, Excel, CSV output
│   └── pipeline.py          ← Orchestrator (ties everything together)
│
├── src/models/              ← v2.0 code (uses heavy paid/local models)
├── src/validation/          ← v2.0 validation framework
├── src/preprocessing/       ← v2.0 preprocessing pipeline
├── src/export/              ← v2.0 export handlers
│
├── data/input/INVOICES/     ← Input invoice files
│   ├── IMAGES/              ← 20 image invoices (JPG, PNG)
│   └── PDF/                 ← 76 PDF invoices (GST001-GST26047.pdf)
│
├── outputs/extractions/     ← Output directory for results
│
├── config/                  ← YAML configuration files
│   ├── settings.yaml        ← v1.0 config
│   └── models_2026.yaml     ← v2.0 config
│
└── docs/                    ← Documentation
    └── STUDY_GUIDE.md       ← This file!
```

### Module Dependency Graph

```
  run_baseline.py
       │
       └──► pipeline.py
              │
              ├──► document_loader.py  (no dependencies on other baseline modules)
              │
              ├──► text_extractor.py   (no dependencies on other baseline modules)
              │
              ├──► field_extractor.py  ──► result.py
              │
              ├──► table_extractor.py  ──► result.py
              │
              ├──► postprocessor.py    ──► result.py
              │
              ├──► export.py           ──► result.py
              │
              └──► result.py           (core data structures, no dependencies)
```

### How Each File Relates

| File | Inputs | Outputs | External Libraries |
|------|--------|---------|-------------------|
| document_loader.py | File path | LoadedDocument | pdfplumber, PyMuPDF, Pillow |
| text_extractor.py | LoadedDocument | ExtractedText | pdfplumber, pytesseract, Pillow, numpy |
| field_extractor.py | Text + Image | Populates InvoiceResult.headers | transformers (LayoutLM) |
| table_extractor.py | Text + Tables | Populates InvoiceResult.line_items | (regex only) |
| postprocessor.py | InvoiceResult | Modified InvoiceResult | (regex, datetime only) |
| export.py | List[InvoiceResult] | JSON, Excel, CSV files | openpyxl, csv, json |
| pipeline.py | Input directory | List[InvoiceResult] + files | (orchestrates others) |
| run_baseline.py | CLI args | Calls pipeline | argparse, logging |

---

## 9. How to Run the System

### Prerequisites

1. **Python 3.8+** (we use 3.10+)
2. **Tesseract OCR** installed on your system
3. Python packages installed (see below)

### Installation Commands

```bash
# 1. Activate virtual environment
cd "c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate   # Linux/Mac

# 2. Install required packages
pip install pdfplumber PyMuPDF pytesseract Pillow openpyxl numpy transformers torch

# 3. Verify Tesseract is installed
tesseract --version
# Expected: tesseract v5.x.x

# 4. If Tesseract is not found, install it:
#    Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
#    Linux: sudo apt install tesseract-ocr
#    Mac: brew install tesseract
```

### Running the Pipeline

```bash
# Navigate to project directory
cd "c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

# Process ALL invoices (PDFs + images)
python run_baseline.py

# Process only PDFs
python run_baseline.py --input data/input/INVOICES/PDF

# Process only images
python run_baseline.py --input data/input/INVOICES/IMAGES

# Process a SINGLE file
python run_baseline.py --file data/input/INVOICES/PDF/GST001.pdf

# Process first 5 files only (good for testing)
python run_baseline.py --max-files 5

# Disable LayoutLM model (faster, regex only)
python run_baseline.py --no-layoutlm

# Export only JSON format
python run_baseline.py --format json

# Show debug-level logging
python run_baseline.py --log-level DEBUG
```

### Expected Output

```
╔══════════════════════════════════════════════════════════════╗
║           BASELINE INVOICE EXTRACTION PIPELINE              ║
║                       Version 3.0.0                         ║
╚══════════════════════════════════════════════════════════════╝

14:30:01 │ INFO     │ Baseline pipeline initialized
14:30:01 │ INFO     │   LayoutLM: enabled
14:30:01 │ INFO     │ Found 96 invoice files in data/input/INVOICES
14:30:01 │ INFO     │ [1/96] Processing: GST001.pdf
14:30:01 │ INFO     │   Type: DIGITAL PDF (1 pages)
14:30:01 │ INFO     │   → Extracted 10 fields, 5 line items
14:30:02 │ INFO     │ [2/96] Processing: GST002.pdf
...

============================================================
EXTRACTION COMPLETE
============================================================
  Files processed: 96
  Total time: 48.3s
  Average time/file: 0.5s

  Output files:
    json: outputs/extractions/baseline_20260219_143050.json
    excel: outputs/extractions/baseline_20260219_143050.xlsx
    csv_headers: outputs/extractions/baseline_headers_20260219_143050.csv
    csv_items: outputs/extractions/baseline_items_20260219_143050.csv
============================================================
```

---

## 10. Bugs Found & Lessons Learned

During the code review of the existing v1.0 and v2.0 code, we found **17 bugs**. These are documented here as learning material.

### Critical Bugs (Would Crash)

| # | File | Bug | Lesson |
|---|------|-----|--------|
| 1 | main_2026.py | Accesses `quality.overall_quality` but attribute is `overall_score` | Always verify attribute names match the class definition |
| 2 | api_service_2026.py | Same `overall_quality` vs `overall_score` bug | Copy-paste errors propagate — always test after copying code |
| 3 | export_handlers_2026.py | References `extraction.model_used` but it's `model_name` | Use IDE autocomplete or type hints to catch these |
| 4 | export_handlers_2026.py | References `extraction.quality_metadata` — doesn't exist | Write tests that actually exercise the export code |
| 5 | export_handlers_2026.py | References `extraction.processing_time_ms` but it's `processing_time_seconds` | Consistent naming convention prevents this |
| 6 | export_handlers_2026.py | References `item.unit_of_measure` — doesn't exist on LineItemOutput | Dataclass fields should be reviewed before use |

### Logic Bugs (Wrong Results)

| # | File | Bug | Lesson |
|---|------|-----|--------|
| 7 | framework_2026.py | Config looks for `rag_validation` but YAML has `rag` | Keep config keys consistent between code and YAML |
| 8 | ground_truth.py | Expects `records` key but JSON has `invoices` | Test data loaders against actual data files |
| 9 | pipeline_2026.py | `_detect_skew` doesn't actually rotate image | Implement logic fully or don't include the function |
| 10 | config/__init__.py | Singleton silently ignores second config path | Singletons should warn or raise on re-initialization |

### Design Issues (Not Bugs, But Problematic)

| # | Issue | Lesson |
|---|-------|--------|
| 11 | Custom `FileNotFoundError` shadows Python built-in | Never name exceptions the same as built-in exceptions |
| 12 | Database handler leaks connections | Always use context managers (`with` statements) |
| 13 | line_item.py has broken f-string in `__repr__` | Test `__repr__` and `__str__` methods |
| 14 | Duplicate date parsing in 5+ places | Extract common logic into utility functions |
| 15 | Duplicate fuzzy matching in 3+ places | DRY principle — Don't Repeat Yourself |
| 16 | Missing `vendor_patterns.json` makes RAG non-functional | Document data file dependencies |
| 17 | No working end-to-end test exists | Always have at least one integration test |

### What We Did Differently in v3.0

1. **Clean module design** — each module has clear inputs/outputs
2. **No external API dependencies** — everything runs locally and free
3. **Cross-validated interfaces** — we audited every function call against its definition
4. **Confidence scoring everywhere** — every extracted value knows how certain it is
5. **Graceful degradation** — if LayoutLM isn't available, regex still works

---

## 11. Next Phase: RAG-Enhanced Extraction

### What is RAG?

**RAG (Retrieval-Augmented Generation)** is an AI technique that combines two steps:

```
  STEP 1: RETRIEVE                    STEP 2: GENERATE
  ┌─────────────────────┐            ┌─────────────────────────┐
  │ Search a knowledge  │            │ Use an LLM to generate  │
  │ base for relevant   │     →      │ answers using both the  │
  │ information         │            │ retrieved info AND the  │
  │                     │            │ original question       │
  └─────────────────────┘            └─────────────────────────┘

  Example:
  Question: "What is the vendor for invoice INV-001?"

  Step 1 (Retrieve): Search our database of known vendors
         Found: "ABC Supplies Ltd" has GSTIN 27AABCU9603R1ZM

  Step 2 (Generate): Use LLM to reason:
         "The GSTIN on this invoice matches ABC Supplies Ltd.
          Vendor name field shows 'ABC Sup...' (partially readable).
          High confidence: vendor is ABC Supplies Ltd."
```

### Phase 2 Plan: RAG for Invoice Extraction

```
  ┌──────────────────────────────────────────────────────────┐
  │               PHASE 2: RAG PIPELINE                       │
  │                                                           │
  │  ┌──────────────┐                                        │
  │  │ KNOWLEDGE    │  Contains:                             │
  │  │ BASE         │  • Known vendor names + GSTINs         │
  │  │ (Vector DB)  │  • Common invoice formats              │
  │  │              │  • Previous extraction results          │
  │  │              │  • Correction history                   │
  │  └──────┬───────┘                                        │
  │         │ RETRIEVE similar invoices                       │
  │         ▼                                                │
  │  ┌──────────────────────────────────────────┐            │
  │  │          BASELINE PIPELINE                │            │
  │  │  (Our current v3.0 system)               │            │
  │  │  Load → Text → Fields → Items → Validate │            │
  │  └──────────────────┬───────────────────────┘            │
  │                     │                                    │
  │                     ▼                                    │
  │  ┌──────────────────────────────────────────┐            │
  │  │          RAG VALIDATION LAYER             │            │
  │  │                                           │            │
  │  │  For each uncertain field:                │            │
  │  │  1. Retrieve similar invoices from KB     │            │
  │  │  2. Compare extracted values              │            │
  │  │  3. Use LLM to resolve conflicts          │            │
  │  │  4. Boost or reduce confidence             │            │
  │  └──────────────────┬───────────────────────┘            │
  │                     │                                    │
  │                     ▼                                    │
  │  ┌──────────────────────────────────────────┐            │
  │  │          LEARNING LOOP                    │            │
  │  │                                           │            │
  │  │  After human review:                      │            │
  │  │  1. Store correct extractions in KB       │            │
  │  │  2. Update vendor patterns                │            │
  │  │  3. Fine-tune confidence thresholds       │            │
  │  └──────────────────────────────────────────┘            │
  └──────────────────────────────────────────────────────────┘
```

### Technologies for Phase 2

| Component | Technology Options (as of Feb 2026) |
|-----------|-------------------------------------|
| Vector Database | ChromaDB (local), Pinecone (cloud), FAISS (lightweight) |
| Embedding Model | sentence-transformers/all-MiniLM-L6-v2, OpenAI text-embedding-3 |
| LLM for Reasoning | Gemini 2.0 Flash, Claude 3.5, GPT-4o mini, local: Llama 3.3 70B |
| Multimodal Models | Gemini 2.0 Flash (vision), GPT-4o (vision), local: DeepSeek-VL2 |

### What RAG Would Improve

| Scenario | Baseline (v3.0) | With RAG (v4.0) |
|----------|-----------------|------------------|
| Vendor name partially readable | Returns "ABC Sup..." (low confidence) | Matches GSTIN to known vendor → "ABC Supplies Ltd." (high confidence) |
| Ambiguous date format | Guesses DD/MM or MM/DD | Looks up vendor's usual date format from history |
| Missing field | Returns None | Retrieves from similar invoices by same vendor |
| OCR error in amount | Accepts "8000" | Cross-checks with similar invoices, flags anomaly |

---

## 12. Research References & Further Reading

### Papers

1. **LayoutLMv3** (Huang et al., 2022) — "LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking" — The model we use for document QA.

2. **Donut** (Kim et al., 2022) — "OCR-free Document Understanding Transformer" — Alternative approach that skips OCR entirely (used in v1.0).

3. **DocFormerv2** (Appalaraju et al., 2023) — "DocFormerv2: Local Features for Document Understanding" — Multi-modal document understanding.

### Tools & Libraries

| Resource | URL | Description |
|----------|-----|-------------|
| Tesseract OCR | github.com/tesseract-ocr/tesseract | The OCR engine documentation |
| pdfplumber | github.com/jsvine/pdfplumber | PDF text extraction library |
| HuggingFace Transformers | huggingface.co/docs/transformers | ML model library |
| LayoutLM Model | huggingface.co/impira/layoutlm-document-qa | The specific model we use |

### Tutorials

- **Regex Tutorial**: regexone.com — Interactive regex learning
- **Python Dataclasses**: docs.python.org/3/library/dataclasses.html
- **OCR Best Practices**: tesseract-ocr.github.io/tessdoc/ImproveQuality.html

---

## Summary

We built a **modular, local, free** invoice extraction pipeline that:

1. **Loads** PDFs and images, auto-detecting document type
2. **Extracts text** perfectly (digital PDFs) or via OCR (images)
3. **Finds header fields** using regex patterns + LayoutLM AI
4. **Extracts line items** from tables using pdfplumber + regex
5. **Validates** by cross-checking totals and formatting
6. **Exports** to JSON, Excel, and CSV

The system handles **Indian GST invoices** with special patterns for GSTIN, HSN codes, CGST/SGST tax splitting, and DD/MM/YYYY dates.

**Next step:** Run the pipeline on the 96 test invoices and measure accuracy, then plan the RAG-enhanced Phase 2.

---

*Generated: 2026-02-19 | Baseline v3.0.0 | Invoice Extraction Project*
