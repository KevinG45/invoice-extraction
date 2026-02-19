# Model Selection Report - February 2026 Edition

## Primary Models Selected

### 1. Sarvam Vision 3B (PRIMARY)
- **Release:** February 5, 2026
- **Params:** 3B (0.9B vision encoder + LM)
- **OmniDocBench v1.5:** 93.28%
- **olmOCR-Bench:** 84.3% (beats Gemini 3 Pro & GPT-5.2)
- **Use case:** General invoices, complex layouts, multilingual (22 Indic languages)
- **Access:** FREE API during February 2026 at https://dashboard.sarvam.ai/
- **License:** Free tier (February 2026), then commercial

### 2. DeepSeek-OCR 2 (VERIFICATION)
- **Release:** January 27, 2026
- **Params:** 3B (380M DeepEncoder V2 + 2.6B LM)
- **OmniDocBench v1.5:** 91.09% (SOTA)
- **Reading Order:** 0.057 edit distance (best in industry)
- **Use case:** Multi-page invoices, dense tables, reading order critical
- **Access:** Hugging Face download, local inference
- **License:** MIT (fully open source)

### 3. PaddleOCR-VL 1.5 (FALLBACK)
- **Release:** January 29, 2026
- **Params:** 0.9B (ultra-compact)
- **OmniDocBench v1.5:** 94.5%
- **Use case:** Poor quality scans, stamps/seals, 109 languages
- **Access:** pip install paddleocr>=3.0.0
- **License:** Apache 2.0

### 4. Qwen3-VL 8B (OPTIONAL - Long Documents)
- **Release:** November 2025, updated February 2026
- **Params:** 8B
- **Context:** 256K tokens (industry-leading)
- **Use case:** Very long multi-page invoices (100+ pages)
- **Access:** Hugging Face / Ollama
- **License:** Apache 2.0

## Model Routing Strategy

```
Quality Score >= 0.8 → Sarvam Vision (primary)
    → Verify critical fields with DeepSeek-OCR 2
    → Cross-model consistency check

Quality Score < 0.8 → PaddleOCR-VL 1.5 (specialized for poor quality)
    → Verify with Sarvam Vision if score > 0.5

Multi-page (>5 pages) → DeepSeek-OCR 2 (best reading order)
    → Optional: Qwen3-VL for 100+ page documents

All results → 6-layer validation framework
```

## Anti-Hallucination Framework (6 Layers)

1. **RAG Validation** - Compare against vendor pattern database (35-60% reduction)
2. **Multi-Agent Validation** - 4 specialized agents cross-validate (92% detection)
3. **Q-A-E Validation** - Independent re-extraction for critical fields
4. **Neurosymbolic Rules** - Mathematical consistency enforcement (100% on math)
5. **Calibrated Confidence** - Dynamic thresholds per field criticality
6. **Cross-Model Consistency** - Multi-model agreement scoring

## Performance Targets

| Metric | Target |
|--------|--------|
| Header Accuracy | >= 98% |
| Line Item Accuracy | >= 96% |
| Numerical Consistency | 100% |
| Hallucination Detection | >= 95% |
| False Positive Rate | <= 8% |
| Single Page Speed | <= 4 seconds |
| Batch Processing | >= 150/hour |
