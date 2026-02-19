# BASELINE MODEL BUILD CHECKLIST
# ================================
# Created: 2026-02-19
# Purpose: Track all steps of the baseline extraction model build
# Rule: Check from entry #1 every time before proceeding to avoid deviation

## PHASE 1: DATA STRUCTURES & RESULT TYPES
- [x] 1.1 Create `src/baseline/__init__.py` - package init
- [x] 1.2 Create `src/baseline/result.py` - InvoiceResult, HeaderField, LineItem dataclasses
- [x] 1.3 Verify result types cover all 14 header fields + 8 line item fields

## PHASE 2: DOCUMENT LOADING
- [x] 2.1 Create `src/baseline/document_loader.py`
- [x] 2.2 Support PDF loading (digital + scanned) via PyMuPDF/pdf2image
- [x] 2.3 Support image loading (JPG, PNG, TIFF, BMP)
- [x] 2.4 Auto-detect document type (digital PDF vs scanned PDF vs image)
- [x] 2.5 Multi-page PDF support (process all pages)

## PHASE 3: TEXT EXTRACTION
- [x] 3.1 Create `src/baseline/text_extractor.py`
- [x] 3.2 Digital PDF text extraction via pdfplumber (perfect quality)
- [x] 3.3 Image/scanned OCR via Tesseract
- [x] 3.4 Preprocessing before OCR (deskew, denoise, enhance contrast)
- [x] 3.5 Return text with bounding box positions where available

## PHASE 4: FIELD EXTRACTION (HEADERS)
- [x] 4.1 Create `src/baseline/field_extractor.py`
- [x] 4.2 Regex patterns for: invoice_number, invoice_date, due_date, vendor_name
- [x] 4.3 Regex patterns for: customer_name, total_amount, subtotal, tax_amount
- [x] 4.4 Regex patterns for: currency, vendor_address, vendor_email, vendor_phone
- [x] 4.5 Regex patterns for: customer_address, shipping
- [x] 4.6 Special handling for Indian GST invoice patterns (GSTIN, HSN, SAC)
- [x] 4.7 LayoutLMv3 Document QA integration for semantic extraction
- [x] 4.8 Confidence scoring for each extracted field
- [x] 4.9 Merge regex + model results (prefer higher confidence)

## PHASE 5: LINE ITEM EXTRACTION
- [x] 5.1 Create `src/baseline/table_extractor.py`
- [x] 5.2 pdfplumber table detection for digital PDFs
- [x] 5.3 Regex-based table row parsing for OCR text
- [x] 5.4 Column header detection and mapping
- [x] 5.5 Numeric field parsing (quantity, price, total)
- [x] 5.6 Handle merged cells, multi-line descriptions
- [x] 5.7 Validate line items (quantity × price ≈ total)

## PHASE 6: POST-PROCESSING
- [x] 6.1 Create `src/baseline/postprocessor.py`
- [x] 6.2 Date normalization (multiple formats → YYYY-MM-DD)
- [x] 6.3 Amount normalization (remove currency symbols, fix decimals)
- [x] 6.4 Cross-validation: sum(line_totals) ≈ subtotal
- [x] 6.5 Cross-validation: subtotal + tax ≈ total_amount
- [x] 6.6 Required field check (invoice_number, total_amount mandatory)
- [x] 6.7 Overall confidence score calculation

## PHASE 7: EXPORT
- [x] 7.1 Create `src/baseline/export.py`
- [x] 7.2 JSON export with metadata and confidence scores
- [x] 7.3 Excel export with Headers + Line Items sheets
- [x] 7.4 CSV export (flat headers + separate line items)

## PHASE 8: PIPELINE ORCHESTRATOR
- [x] 8.1 Create `src/baseline/pipeline.py` - main pipeline
- [x] 8.2 End-to-end: load → extract text → extract fields → extract tables → post-process → export
- [x] 8.3 Error handling at every stage
- [x] 8.4 Logging at every stage
- [x] 8.5 Support single file and batch processing

## PHASE 9: MAIN ENTRY POINT
- [x] 9.1 Create `run_baseline.py` at project root
- [x] 9.2 CLI arguments: --input, --output, --format
- [x] 9.3 Summary statistics at the end

## PHASE 10: TESTING
- [ ] 10.1 Test on 2-3 PDF invoices (verify headers + line items)
- [ ] 10.2 Test on 2-3 image invoices
- [ ] 10.3 Verify JSON output is correct
- [ ] 10.4 Verify Excel output is correct
- [ ] 10.5 Calculate accuracy metrics

## PHASE 11: DOCUMENTATION
- [x] 11.1 Study guide created (docs/STUDY_GUIDE.md)
- [x] 11.2 Glossary of all terms
- [x] 11.3 Architecture diagrams (ASCII)
- [x] 11.4 Pipeline flowcharts (ASCII)
- [x] 11.5 Indian GST specifics documented
- [x] 11.6 Next phase (RAG) planning
- [x] 11.7 Bug catalog (17 bugs documented)

## STATUS TRACKING
- Current Phase: PHASES 1-9 + 11 COMPLETE — Ready for PHASE 10 (Testing)
- Last Checked: All phases 1-9 verified + interface audit passed + study guide written
- Deviations: Phase 10 deferred (requires user to run commands)
