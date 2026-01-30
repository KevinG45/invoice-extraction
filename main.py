#!/usr/bin/env python3
"""
Intelligent Invoice Header Extraction System - Main Entry Point.

This is the main entry point for the invoice extraction system.
It provides both a command-line interface and programmatic access
to the extraction pipeline.

Usage:
    Command Line:
        python main.py --input invoice.pdf --output results.xlsx
        python main.py --input ./invoices/ --output ./results/ --evaluate
    
    Python:
        from main import run_extraction
        results = run_extraction("invoice.pdf")

Author: ML Engineering Team
Version: 1.0.0
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import project modules
from config import ConfigurationManager
from src.utils.logger import setup_logger_from_config, get_logger
from src.utils.helpers import ensure_directory, validate_file_exists


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Intelligent Invoice Header Extraction System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Process single invoice:
        python main.py --input invoice.pdf --output results.xlsx
    
    Process directory:
        python main.py --input ./invoices/ --output ./results/
    
    With evaluation:
        python main.py --input ./invoices/ --evaluate --ground-truth data/ground_truth.json
        """
    )
    
    # Input/Output arguments
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input file or directory containing invoices"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="outputs/extraction_results.xlsx",
        help="Output file or directory (default: outputs/extraction_results.xlsx)"
    )
    
    # Processing options
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to custom configuration file"
    )
    
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Disable Excel output"
    )
    
    parser.add_argument(
        "--no-database",
        action="store_true",
        help="Disable database output"
    )
    
    # Evaluation options
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run evaluation after extraction"
    )
    
    parser.add_argument(
        "--ground-truth", "-gt",
        type=str,
        default=None,
        help="Path to ground truth file for evaluation"
    )
    
    # Logging options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress console output"
    )
    
    return parser.parse_args()


def initialize_system(args: argparse.Namespace) -> ConfigurationManager:
    """
    Initialize the extraction system with configuration and logging.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        Initialized configuration manager.
    """
    # Load configuration
    config = ConfigurationManager(args.config)
    
    # Setup logging
    logger = setup_logger_from_config()
    
    if args.debug:
        import logging
        logging.getLogger("invoice_extraction").setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("INTELLIGENT INVOICE HEADER EXTRACTION SYSTEM")
    logger.info("=" * 60)
    logger.info(f"Version: {config.get('project.version', '1.0.0')}")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")
    
    return config


def validate_inputs(args: argparse.Namespace) -> List[Path]:
    """
    Validate input files/directories and return list of files to process.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        List of valid input file paths.
        
    Raises:
        FileNotFoundError: If input path doesn't exist.
    """
    logger = get_logger(__name__)
    input_path = Path(args.input)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    
    # Get list of files to process
    supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    
    if input_path.is_file():
        if input_path.suffix.lower() in supported_extensions:
            return [input_path]
        else:
            raise ValueError(f"Unsupported file type: {input_path.suffix}")
    
    elif input_path.is_dir():
        files = []
        for ext in supported_extensions:
            files.extend(input_path.glob(f"*{ext}"))
            files.extend(input_path.glob(f"*{ext.upper()}"))
        
        if not files:
            logger.warning(f"No supported files found in: {input_path}")
        else:
            logger.info(f"Found {len(files)} files to process")
        
        return sorted(files)
    
    raise ValueError(f"Invalid input path: {input_path}")


def run_extraction(
    input_path: str,
    output_path: Optional[str] = None,
    config_path: Optional[str] = None,
    enable_excel: bool = True,
    enable_database: bool = True,
    evaluate: bool = False,
    ground_truth_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Run the invoice extraction pipeline.
    
    This is the main programmatic entry point for the extraction system.
    It orchestrates all pipeline phases and returns extracted data.
    
    Args:
        input_path: Path to input file or directory.
        output_path: Path for output files.
        config_path: Optional custom configuration file path.
        enable_excel: Whether to generate Excel output.
        enable_database: Whether to save to database.
        evaluate: Whether to run evaluation.
        ground_truth_path: Path to ground truth for evaluation.
        
    Returns:
        List of extracted invoice data dictionaries.
        
    Example:
        >>> results = run_extraction("invoices/", "outputs/")
        >>> for r in results:
        ...     print(r['invoice_number'])
    """
    logger = get_logger(__name__)
    
    # Initialize configuration
    config = ConfigurationManager(config_path)
    
    # Import pipeline components
    from src.input_handler import InputHandler
    from src.ocr_engine import OCREngine
    from src.model_inference import InvoiceExtractor
    from src.postprocessor import PostProcessor
    from src.output_handler import OutputHandler
    
    # Initialize pipeline components
    logger.info("Initializing pipeline components...")
    input_handler = InputHandler()
    ocr_engine = OCREngine()
    extractor = InvoiceExtractor()
    post_processor = PostProcessor()
    output_handler = OutputHandler(
        excel_enabled=enable_excel,
        database_enabled=enable_database
    )
    
    # Get list of files to process
    input_p = Path(input_path)
    supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    
    if input_p.is_file():
        files_to_process = [input_p]
    else:
        files_to_process = []
        for ext in supported_extensions:
            files_to_process.extend(input_p.glob(f"*{ext}"))
            files_to_process.extend(input_p.glob(f"*{ext.upper()}"))
        files_to_process = sorted(files_to_process)
    
    logger.info(f"Processing {len(files_to_process)} files...")
    
    # Process each file through the pipeline
    extraction_results = []
    
    for file_path in files_to_process:
        logger.info(f"Processing: {file_path.name}")
        
        try:
            # Phase 1: Input handling - load and normalize document
            document = input_handler.load(str(file_path))
            
            # Process each page (for multi-page documents)
            images = document.images if hasattr(document, 'images') else []
            
            for page_idx, image in enumerate(images):
                if image is None:
                    continue
                    
                logger.debug(f"Processing page {page_idx + 1}")
                
                # Phase 2: OCR processing
                ocr_result = ocr_engine.extract(image)
                
                # Phase 3: Model inference - extract fields
                extraction = extractor.extract(
                    image=image,
                    ocr_result=ocr_result,
                    source_file=str(file_path)
                )
                
                # Phase 4: Post-processing - normalize and validate
                processed_result = post_processor.process(extraction)
                
                extraction_results.append(processed_result)
                
                logger.info(
                    f"  Extracted: Invoice #{processed_result.invoice_number or 'N/A'}, "
                    f"Confidence: {processed_result.average_confidence:.2f}"
                )
        
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            continue
    
    # Phase 5: Output generation
    if extraction_results:
        logger.info("Generating outputs...")
        
        # Determine output filename
        output_filename = None
        if output_path:
            output_p = Path(output_path)
            if output_p.suffix == '.xlsx':
                output_filename = output_p.name
        
        output_info = output_handler.save(
            extraction_results,
            excel_filename=output_filename
        )
        
        if output_info.get('excel_path'):
            logger.info(f"Excel output: {output_info['excel_path']}")
        
        if output_info.get('database_records'):
            db_info = output_info['database_records']
            logger.info(
                f"Database: {db_info['inserted']} inserted, "
                f"{db_info['skipped']} skipped"
            )
    
    # Phase 6: Evaluation (if enabled)
    if evaluate and ground_truth_path:
        logger.info("Evaluation will be implemented in Phase 6")
    
    # Return results as dictionaries
    results = [r.to_dict() for r in extraction_results]
    
    return results


def main() -> int:
    """
    Main function - entry point for command-line execution.
    
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()
        
        # Initialize system
        config = initialize_system(args)
        logger = get_logger(__name__)
        
        # Validate inputs
        input_files = validate_inputs(args)
        
        if not input_files:
            logger.error("No files to process")
            return 1
        
        # Ensure output directory exists
        output_path = Path(args.output)
        if output_path.suffix:
            # It's a file, ensure parent directory exists
            ensure_directory(output_path.parent)
        else:
            # It's a directory
            ensure_directory(output_path)
        
        # Run extraction
        results = run_extraction(
            input_path=args.input,
            output_path=args.output,
            config_path=args.config,
            enable_excel=not args.no_excel,
            enable_database=not args.no_database,
            evaluate=args.evaluate,
            ground_truth_path=args.ground_truth
        )
        
        logger.info("=" * 60)
        logger.info(f"Extraction complete. Processed {len(input_files)} files.")
        logger.info("=" * 60)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
        
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
