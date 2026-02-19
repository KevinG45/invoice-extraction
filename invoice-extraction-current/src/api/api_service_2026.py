"""
FastAPI REST API Service for Invoice Extraction (2026)

Endpoints:
  POST /extract          - Single invoice extraction
  POST /extract/batch    - Batch invoice extraction
  GET  /health           - Health check
  GET  /models           - List available models
  GET  /config           - Current configuration

Author: ML Engineering Team
Version: 2.0.0
"""

import io
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("invoice_extraction.api")

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FieldValueSchema(BaseModel):
    value: Optional[Any] = None
    confidence: float = 0.0
    uncertain: bool = False
    verified: bool = False
    validation_method: Optional[str] = None
    source_model: Optional[str] = None


class LineItemSchema(BaseModel):
    line_number: int
    description: FieldValueSchema
    quantity: FieldValueSchema
    unit_price: FieldValueSchema
    line_total: FieldValueSchema
    item_code: Optional[FieldValueSchema] = None
    unit_of_measure: Optional[FieldValueSchema] = None
    tax_rate: Optional[FieldValueSchema] = None


class ExtractionResponseSchema(BaseModel):
    request_id: str
    source_file: str
    headers: Dict[str, FieldValueSchema]
    line_items: List[LineItemSchema]
    overall_confidence: float
    model_used: Optional[str] = None
    processing_time_ms: int
    validation_report: Optional[Dict[str, Any]] = None
    quality_metadata: Optional[Dict[str, Any]] = None


class BatchResponseSchema(BaseModel):
    request_id: str
    total_files: int
    successful: int
    failed: int
    results: List[ExtractionResponseSchema]
    total_processing_time_ms: int


class HealthSchema(BaseModel):
    status: str
    version: str
    timestamp: str
    models_available: List[str]


class ErrorSchema(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app(config: Optional[Dict[str, Any]] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: System configuration dict (from models_2026.yaml)

    Returns:
        Configured FastAPI app
    """
    config = config or {}
    api_config = config.get("api", {})

    app = FastAPI(
        title="Invoice Extraction API",
        description=(
            "Production-ready invoice extraction system using 2026 "
            "state-of-the-art vision-language models with 6-layer "
            "anti-hallucination validation."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    cors_origins = api_config.get("cors_origins", ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store config and lazy-initialized pipeline
    app.state.config = config
    app.state.pipeline = None

    # ------------------------------------------------------------------
    # Helper: get or initialize pipeline
    # ------------------------------------------------------------------
    def _get_pipeline():
        """Lazy-initialize the extraction pipeline."""
        if app.state.pipeline is None:
            try:
                from src.models.model_router import ModelRouter
                from src.preprocessing.pipeline_2026 import PreprocessingPipeline2026
                from src.validation.framework_2026 import ValidationFramework2026
                from src.export.export_handlers_2026 import ExportManager2026

                pipeline = {
                    "router": ModelRouter(config),
                    "preprocessor": PreprocessingPipeline2026(config),
                    "validator": ValidationFramework2026(config),
                    "exporter": ExportManager2026(config),
                }

                # Initialize models
                pipeline["router"].initialize_models()

                app.state.pipeline = pipeline
                logger.info("API pipeline initialized successfully")
            except Exception as e:
                logger.error(f"Pipeline initialization failed: {e}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Pipeline not ready: {str(e)}",
                )
        return app.state.pipeline

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @app.get("/health", response_model=HealthSchema)
    async def health_check():
        """Health check endpoint."""
        models = []
        try:
            pipeline = _get_pipeline()
            models = list(pipeline["router"].models.keys())
        except Exception:
            pass

        return HealthSchema(
            status="healthy",
            version="2.0.0",
            timestamp=datetime.now().isoformat(),
            models_available=models,
        )

    @app.get("/models")
    async def list_models():
        """List available extraction models."""
        try:
            pipeline = _get_pipeline()
            model_info = {}
            for name, model in pipeline["router"].models.items():
                model_info[name] = {
                    "available": model.is_available(),
                    "type": type(model).__name__,
                }
            return {"models": model_info}
        except Exception as e:
            return {"models": {}, "error": str(e)}

    @app.get("/config")
    async def get_config():
        """Return current (non-sensitive) configuration."""
        safe_config = {
            k: v for k, v in config.items()
            if k not in ("api_keys", "secrets")
        }
        return {"config": safe_config}

    @app.post("/extract", response_model=ExtractionResponseSchema)
    async def extract_invoice(
        file: UploadFile = File(...),
        model: Optional[str] = Query(
            None, description="Force a specific model"
        ),
        skip_validation: bool = Query(
            False, description="Skip validation layers"
        ),
    ):
        """
        Extract data from a single invoice image or PDF.

        Accepts JPEG, PNG, TIFF, or PDF files.
        """
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Validate file type
        allowed_types = {
            "image/jpeg", "image/png", "image/tiff",
            "application/pdf", "image/bmp",
        }
        content_type = file.content_type or ""
        filename = file.filename or "unknown"

        # Infer from extension if content type unclear
        ext = os.path.splitext(filename)[1].lower()
        ext_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".tiff": "image/tiff",
            ".tif": "image/tiff", ".pdf": "application/pdf",
            ".bmp": "image/bmp",
        }
        if content_type not in allowed_types:
            content_type = ext_map.get(ext, content_type)

        if content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. "
                       f"Supported: JPEG, PNG, TIFF, PDF",
            )

        try:
            pipeline = _get_pipeline()

            # Read file
            file_bytes = await file.read()

            # Convert to PIL Image
            from PIL import Image

            if content_type == "application/pdf":
                # Convert first page of PDF to image
                images = _pdf_to_images(file_bytes)
                if not images:
                    raise HTTPException(400, "Could not convert PDF to images")
                image = images[0]
            else:
                image = Image.open(io.BytesIO(file_bytes))

            # Preprocess
            processed, quality = pipeline["preprocessor"].process(image)

            # Extract
            extraction = pipeline["router"].extract(
                processed,
                source_file=filename,
                quality_score=quality.overall_quality,
            )

            # Validate
            if not skip_validation:
                validation_report = pipeline["validator"].validate(
                    extraction, image=processed
                )
            else:
                validation_report = None

            # Build response
            processing_time = int((time.time() - start_time) * 1000)
            extraction.processing_time_ms = processing_time

            response = _extraction_to_response(
                extraction, request_id, filename,
                processing_time, validation_report,
                quality.to_dict() if hasattr(quality, "to_dict") else {},
            )

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Extraction failed [{request_id}]: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed: {str(e)}",
            )

    @app.post("/extract/batch", response_model=BatchResponseSchema)
    async def extract_batch(
        files: List[UploadFile] = File(...),
        skip_validation: bool = Query(False),
    ):
        """Extract data from multiple invoice files."""
        request_id = str(uuid.uuid4())[:8]
        batch_start = time.time()

        max_batch = api_config.get("max_batch_size", 50)
        if len(files) > max_batch:
            raise HTTPException(
                status_code=400,
                detail=f"Max batch size is {max_batch}, got {len(files)} files",
            )

        results = []
        successful = 0
        failed = 0

        for file in files:
            try:
                # Re-use single extraction logic
                result = await extract_invoice(
                    file=file,
                    skip_validation=skip_validation,
                )
                results.append(result)
                successful += 1
            except Exception as e:
                failed += 1
                logger.error(f"Batch item failed: {file.filename}: {e}")

        total_time = int((time.time() - batch_start) * 1000)

        return BatchResponseSchema(
            request_id=request_id,
            total_files=len(files),
            successful=successful,
            failed=failed,
            results=results,
            total_processing_time_ms=total_time,
        )

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pdf_to_images(pdf_bytes: bytes) -> list:
    """Convert PDF bytes to list of PIL Images."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            from PIL import Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except ImportError:
        pass

    try:
        from pdf2image import convert_from_bytes
        return convert_from_bytes(pdf_bytes, dpi=300)
    except ImportError:
        logger.error("Neither PyMuPDF nor pdf2image available for PDF conversion")
        return []


def _extraction_to_response(
    extraction,
    request_id: str,
    filename: str,
    processing_time: int,
    validation_report: Optional[Dict],
    quality_metadata: Optional[Dict],
) -> ExtractionResponseSchema:
    """Convert ExtractionOutput to API response schema."""
    from src.models.base_extractor import ExtractionOutput

    headers = {}
    for field_name in ExtractionOutput.HEADER_FIELDS:
        fv = extraction.get_field(field_name)
        if fv:
            headers[field_name] = FieldValueSchema(
                value=fv.value,
                confidence=round(fv.confidence, 1),
                uncertain=fv.uncertain,
                verified=fv.verified,
                validation_method=fv.validation_method,
                source_model=fv.source_model,
            )

    line_items = []
    for item in extraction.line_items:
        li = LineItemSchema(
            line_number=item.line_number,
            description=FieldValueSchema(
                value=item.description.value,
                confidence=round(item.description.confidence, 1),
            ),
            quantity=FieldValueSchema(
                value=item.quantity.value,
                confidence=round(item.quantity.confidence, 1),
            ),
            unit_price=FieldValueSchema(
                value=item.unit_price.value,
                confidence=round(item.unit_price.confidence, 1),
            ),
            line_total=FieldValueSchema(
                value=item.line_total.value,
                confidence=round(item.line_total.confidence, 1),
            ),
        )
        line_items.append(li)

    return ExtractionResponseSchema(
        request_id=request_id,
        source_file=filename,
        headers=headers,
        line_items=line_items,
        overall_confidence=round(
            extraction.calculate_overall_confidence(), 1
        ),
        model_used=extraction.model_used,
        processing_time_ms=processing_time,
        validation_report=validation_report,
        quality_metadata=quality_metadata,
    )


# ---------------------------------------------------------------------------
# CLI launcher
# ---------------------------------------------------------------------------

def run_api(config: Optional[Dict[str, Any]] = None, host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    import uvicorn

    app = create_app(config)
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import yaml

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "models_2026.yaml"
    )
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    run_api(config)
