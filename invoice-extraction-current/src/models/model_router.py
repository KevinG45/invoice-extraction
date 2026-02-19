"""
Model Router - Intelligent routing between 2026 models.

Routes invoices to the optimal model based on:
- Image quality score
- Page count
- Document characteristics
- Model availability

Author: ML Engineering Team
Version: 2.0.0
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from src.models.base_extractor import BaseExtractor, ExtractionOutput, FieldValue

logger = logging.getLogger("invoice_extraction.models.router")


class ModelRouter:
    """
    Intelligent model router for 2026 invoice extraction.

    Routing Strategy:
    - High quality (>= 0.8): Sarvam Vision → verify with DeepSeek-OCR 2
    - Low quality (< 0.8): PaddleOCR-VL 1.5 → verify with Sarvam if score > 0.5
    - Multi-page (>5): DeepSeek-OCR 2 (best reading order)
    - Very long (>50): Qwen3-VL (256K context)

    Supports cross-model verification for critical fields.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.routing_config = config.get("routing", {})

        # Quality thresholds
        self.quality_high = self.routing_config.get("quality_threshold_high", 0.8)
        self.quality_low = self.routing_config.get("quality_threshold_low", 0.5)

        # Page thresholds
        self.multipage_threshold = self.routing_config.get("multipage_threshold", 5)
        self.long_doc_threshold = self.routing_config.get("long_document_threshold", 50)

        # Strategy
        self.strategy = self.routing_config.get("strategy", "quality_based")
        self.verify_critical = self.routing_config.get("verify_critical_fields", True)
        self.critical_fields = self.routing_config.get(
            "critical_fields", ["invoice_number", "total_amount", "invoice_date"]
        )

        # Models (lazy-loaded)
        self._models: Dict[str, BaseExtractor] = {}
        self._model_configs = config.get("models", {})

    def register_model(self, role: str, extractor: BaseExtractor) -> None:
        """Register a model extractor for a specific role."""
        self._models[role] = extractor
        logger.info(f"Registered model '{extractor.model_name}' as '{role}'")

    def initialize_models(self) -> Dict[str, bool]:
        """
        Initialize all configured models and return availability status.
        """
        status = {}

        # Initialize Sarvam Vision (primary)
        sarvam_config = self._model_configs.get("sarvam_vision", {})
        if sarvam_config.get("enabled", False):
            try:
                from src.models.sarvam_vision import SarvamVisionExtractor
                extractor = SarvamVisionExtractor(sarvam_config)
                available = extractor.is_available()
                if available:
                    self.register_model("primary", extractor)
                status["sarvam_vision"] = available
            except Exception as e:
                logger.error(f"Failed to init Sarvam Vision: {e}")
                status["sarvam_vision"] = False

        # Initialize DeepSeek-OCR 2 (verification)
        deepseek_config = self._model_configs.get("deepseek_ocr2", {})
        if deepseek_config.get("enabled", False):
            try:
                from src.models.deepseek_ocr2 import DeepSeekOCR2Extractor
                extractor = DeepSeekOCR2Extractor(deepseek_config)
                available = extractor.is_available()
                if available:
                    self.register_model("verification", extractor)
                status["deepseek_ocr2"] = available
            except Exception as e:
                logger.error(f"Failed to init DeepSeek-OCR 2: {e}")
                status["deepseek_ocr2"] = False

        # Initialize PaddleOCR-VL 1.5 (fallback)
        paddle_config = self._model_configs.get("paddleocr_vl", {})
        if paddle_config.get("enabled", False):
            try:
                from src.models.paddleocr_vl import PaddleOCRVLExtractor
                extractor = PaddleOCRVLExtractor(paddle_config)
                available = extractor.is_available()
                if available:
                    self.register_model("fallback", extractor)
                status["paddleocr_vl"] = available
            except Exception as e:
                logger.error(f"Failed to init PaddleOCR-VL: {e}")
                status["paddleocr_vl"] = False

        if not self._models:
            logger.warning("No models available! Check configuration and installations.")

        return status

    def extract(
        self,
        image: Image.Image,
        quality_score: float = 1.0,
        page_count: int = 1,
        **kwargs,
    ) -> ExtractionOutput:
        """
        Route extraction to the optimal model based on input characteristics.

        Args:
            image: PIL Image of invoice page.
            quality_score: Image quality assessment (0.0-1.0).
            page_count: Total number of pages in the document.
            **kwargs: Additional parameters (source_file, page_number, etc.)

        Returns:
            ExtractionOutput with extraction results and validation metadata.
        """
        start_time = time.time()

        # Select primary model based on routing strategy
        primary_model, selection_reason = self._select_model(
            quality_score, page_count
        )

        if primary_model is None:
            output = ExtractionOutput(
                source_file=kwargs.get("source_file", ""),
                extraction_timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            output.errors.append("No models available for extraction")
            return output

        logger.info(
            f"Routing to {primary_model.model_name} "
            f"(quality={quality_score:.2f}, pages={page_count}, "
            f"reason={selection_reason})"
        )

        # Primary extraction
        kwargs["quality_score"] = quality_score
        result = primary_model.extract(image, **kwargs)

        # Cross-model verification for critical fields
        if self.verify_critical and self._should_verify(result):
            verification_model = self._get_verification_model(primary_model)
            if verification_model:
                result = self._cross_verify(
                    result, image, verification_model, **kwargs
                )

        result.processing_time_seconds = time.time() - start_time
        result.image_quality_score = quality_score
        return result

    def extract_with_ensemble(
        self, image: Image.Image, **kwargs
    ) -> ExtractionOutput:
        """
        Extract using all available models and combine results.

        Uses majority voting for final values.
        Best for maximum accuracy on critical documents.
        """
        results = []

        for role, model in self._models.items():
            try:
                result = model.extract(image, **kwargs)
                results.append((role, result))
                logger.info(
                    f"Ensemble: {model.model_name} extracted "
                    f"{len(result.extracted_fields)} fields"
                )
            except Exception as e:
                logger.error(f"Ensemble: {model.model_name} failed: {e}")

        if not results:
            output = ExtractionOutput()
            output.errors.append("All models failed in ensemble extraction")
            return output

        if len(results) == 1:
            return results[0][1]

        # Combine results using majority voting
        return self._majority_vote(results)

    def _select_model(
        self, quality_score: float, page_count: int
    ) -> Tuple[Optional[BaseExtractor], str]:
        """Select the optimal model based on routing strategy."""

        if self.strategy == "always_primary":
            model = self._models.get("primary")
            if model:
                return model, "always_primary strategy"

        if self.strategy == "ensemble":
            # Return primary but caller should use extract_with_ensemble
            model = self._models.get("primary")
            if model:
                return model, "ensemble strategy"

        # Quality-based routing (default)
        if page_count > self.long_doc_threshold:
            # Very long documents - prefer Qwen3-VL if available
            model = self._models.get("long_document")
            if model:
                return model, f"long document ({page_count} pages)"

        if page_count > self.multipage_threshold:
            # Multi-page - prefer DeepSeek-OCR 2 for reading order
            model = self._models.get("verification")
            if model:
                return model, f"multi-page ({page_count} pages, best reading order)"

        if quality_score >= self.quality_high:
            # High quality - use primary (Sarvam Vision)
            model = self._models.get("primary")
            if model:
                return model, f"high quality ({quality_score:.2f})"

        if quality_score < self.quality_high:
            # Lower quality - use PaddleOCR-VL 1.5
            model = self._models.get("fallback")
            if model:
                return model, f"lower quality ({quality_score:.2f})"

        # Fallback to any available model
        for role in ["primary", "verification", "fallback"]:
            model = self._models.get(role)
            if model:
                return model, f"fallback to {role} (no better option)"

        return None, "no models available"

    def _should_verify(self, result: ExtractionOutput) -> bool:
        """Determine if cross-model verification is needed."""
        # Always verify if there are uncertain critical fields
        for field_name in self.critical_fields:
            fv = result.get_field(field_name)
            if fv and (fv.uncertain or fv.confidence < 85):
                return True

        # Verify if overall confidence is low
        if result.overall_confidence < 0.85:
            return True

        # Verify if there are errors or warnings
        if result.errors:
            return True

        return False

    def _get_verification_model(
        self, primary_model: BaseExtractor
    ) -> Optional[BaseExtractor]:
        """Get a different model for verification."""
        for role, model in self._models.items():
            if model is not primary_model:
                return model
        return None

    def _cross_verify(
        self,
        primary_result: ExtractionOutput,
        image: Image.Image,
        verification_model: BaseExtractor,
        **kwargs,
    ) -> ExtractionOutput:
        """
        Cross-verify critical fields using a second model.

        Updates the primary result with verification metadata.
        """
        logger.info(
            f"Cross-verifying with {verification_model.model_name}..."
        )

        try:
            verification_result = verification_model.extract(image, **kwargs)

            # Compare critical fields
            agreements = 0
            disagreements = 0
            verification_details = {}

            for field_name in self.critical_fields:
                primary_fv = primary_result.get_field(field_name)
                verify_fv = verification_result.get_field(field_name)

                if primary_fv and verify_fv:
                    # Compare values
                    primary_val = str(primary_fv.value or "").strip().lower()
                    verify_val = str(verify_fv.value or "").strip().lower()

                    if primary_val == verify_val:
                        agreements += 1
                        primary_fv.verified = True
                        primary_fv.validation_method = "cross_model"
                    else:
                        disagreements += 1
                        # Use the value with higher confidence
                        if verify_fv.confidence > primary_fv.confidence:
                            primary_fv.value = verify_fv.value
                            primary_fv.confidence = (
                                primary_fv.confidence + verify_fv.confidence
                            ) / 2
                            primary_fv.uncertain = True
                            primary_result.warnings.append(
                                f"{field_name}: updated from verification model "
                                f"('{primary_val}' → '{verify_val}')"
                            )
                        else:
                            primary_fv.uncertain = True
                            primary_result.warnings.append(
                                f"{field_name}: verification disagreement "
                                f"(primary='{primary_val}', verify='{verify_val}')"
                            )

                    verification_details[field_name] = {
                        "primary_value": primary_fv.value,
                        "verification_value": verify_fv.value,
                        "agreed": primary_val == verify_val,
                        "primary_confidence": primary_fv.confidence,
                        "verification_confidence": verify_fv.confidence,
                    }

            total = agreements + disagreements
            agreement_score = agreements / total if total > 0 else 0.0

            primary_result.validation_results["cross_model_verification"] = {
                "verification_model": verification_model.model_name,
                "agreement_score": agreement_score,
                "agreements": agreements,
                "disagreements": disagreements,
                "details": verification_details,
            }

            logger.info(
                f"Cross-verification: {agreements}/{total} fields agreed "
                f"(score={agreement_score:.2f})"
            )

        except Exception as e:
            logger.error(f"Cross-verification failed: {e}")
            primary_result.warnings.append(
                f"Cross-verification failed: {str(e)}"
            )

        return primary_result

    def _majority_vote(
        self, results: List[Tuple[str, ExtractionOutput]]
    ) -> ExtractionOutput:
        """Combine multiple extraction results using majority voting."""
        # Use the result with highest overall confidence as base
        best_result = max(results, key=lambda x: x[1].overall_confidence)
        output = best_result[1]

        # For each field, check agreement across models
        for field_name in ExtractionOutput.HEADER_FIELDS:
            values = []
            for role, result in results:
                fv = result.get_field(field_name)
                if fv and fv.value is not None:
                    values.append({
                        "value": fv.value,
                        "confidence": fv.confidence,
                        "model": result.model_name,
                    })

            if len(values) >= 2:
                # Check agreement
                unique_values = set(
                    str(v["value"]).strip().lower() for v in values
                )
                if len(unique_values) == 1:
                    # All agree - boost confidence
                    fv = output.get_field(field_name)
                    if fv:
                        fv.confidence = min(100, fv.confidence * 1.1)
                        fv.verified = True
                        fv.validation_method = "ensemble_agreement"
                else:
                    # Disagreement - use highest confidence
                    best_value = max(values, key=lambda x: x["confidence"])
                    fv = output.get_field(field_name)
                    if fv:
                        fv.value = best_value["value"]
                        fv.confidence = best_value["confidence"]
                        fv.uncertain = True
                        output.warnings.append(
                            f"{field_name}: ensemble disagreement, "
                            f"used {best_value['model']} value"
                        )

        # Ensemble metadata
        output.validation_results["ensemble"] = {
            "models_used": [r[1].model_name for _, r in zip(range(len(results)), results)],
            "model_count": len(results),
            "strategy": "majority_vote",
        }

        output.calculate_overall_confidence()
        return output

    @property
    def available_models(self) -> List[str]:
        """List available model roles."""
        return list(self._models.keys())

    @property
    def model_count(self) -> int:
        """Number of registered models."""
        return len(self._models)
