"""
PuranGPT — Text Extractor
===========================
Extracts textual content from PDF files of Hindu sacred texts.

Strategy
--------
1. **PyMuPDF (fitz)** — fast, high-quality extraction for PDFs with embedded
   text layer (most modern/digital PDFs).
2. **PaddleOCR fallback** — invoked when average text per page is below
   threshold, indicating a scanned/image-based PDF.  PaddleOCR is configured
   for Hindi (`lang='hi'`) which covers Devanagari script used for Sanskrit.
3. **OpenCV preprocessing** — applied before OCR: deskew, binarize (Otsu
   threshold), and denoise (fastNlMeansDenoising) to maximize OCR accuracy.

Output
------
Per-PDF JSON files saved under ``output_dir/{purana_name}/{filename}.json``:

.. code-block:: json

    {
        "source_file": "bhagavata.pdf",
        "source_path": "/abs/path/bhagavata.pdf",
        "total_pages": 1024,
        "extraction_method": "pymupdf",  // or "paddleocr" or "hybrid"
        "pages": {
            "1": {
                "text": "...",
                "confidence": 0.95,
                "method": "pymupdf",
                "word_count": 120
            },
            ...
        }
    }

Usage
-----
    extractor = TextExtractor(lang='hi', dpi=200, min_text_per_page=100)
    result = extractor.extract_pdf(Path("data/raw_pdfs/bhagavata/bhagavata.pdf"))
    extractor.extract_all(Path("data/raw_pdfs"), Path("data/extracted"))
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TaskID, SpinnerColumn
from rich.logging import RichHandler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("purangpt.extractor")
console = Console()

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PageResult:
    """Extraction result for a single PDF page."""
    page_num: int           # 1-indexed
    text: str               # Extracted text
    confidence: float       # 0.0 – 1.0 (1.0 for PyMuPDF since it has no OCR confidence)
    method: str             # 'pymupdf' | 'paddleocr' | 'empty'
    word_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split()) if self.text else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "word_count": self.word_count,
        }


@dataclass
class PDFResult:
    """Extraction result for an entire PDF file."""
    source_file: str
    source_path: str
    total_pages: int
    extraction_method: str          # 'pymupdf' | 'paddleocr' | 'hybrid'
    pages: Dict[str, PageResult]    # key = str(page_num) for JSON serialisability
    extraction_time_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_path": self.source_path,
            "total_pages": self.total_pages,
            "extraction_method": self.extraction_method,
            "extraction_time_sec": round(self.extraction_time_sec, 2),
            "pages": {k: v.to_dict() for k, v in self.pages.items()},
        }


# ---------------------------------------------------------------------------
# OpenCV image preprocessing helpers
# ---------------------------------------------------------------------------

class ImagePreprocessor:
    """
    Prepares PDF-page images for OCR using OpenCV.

    Pipeline
    --------
    1. Grayscale conversion
    2. Deskew (compute skew angle via Hough lines, rotate)
    3. Adaptive binarization (Otsu threshold)
    4. Morphological denoising
    """

    @staticmethod
    def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV BGR numpy array."""
        rgb = np.array(pil_img.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    @staticmethod
    def cv2_to_pil(cv2_img: np.ndarray) -> Image.Image:
        """Convert OpenCV BGR numpy array to PIL Image (RGB)."""
        rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @staticmethod
    def to_gray(img: np.ndarray) -> np.ndarray:
        """Convert BGR image to grayscale."""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img  # Already gray

    @staticmethod
    def compute_skew_angle(gray: np.ndarray) -> float:
        """
        Compute the skew angle of text in an image (degrees).

        Uses edge detection + Hough transform to find dominant line angle.
        Returns 0.0 if skew cannot be determined reliably.
        """
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        # Hough line transform
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi / 180,
            threshold=100, minLineLength=100, maxLineGap=10
        )
        if lines is None or len(lines) < 5:
            return 0.0

        angles: List[float] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 == 0:
                continue
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            # Only consider near-horizontal lines (text lines)
            if -45 < angle < 45:
                angles.append(angle)

        if not angles:
            return 0.0
        return float(np.median(angles))

    @classmethod
    def deskew(cls, img: np.ndarray) -> np.ndarray:
        """
        Deskew an image by rotating it to align text horizontally.

        Skips rotation if skew angle is less than 0.5°.
        """
        gray = cls.to_gray(img)
        angle = cls.compute_skew_angle(gray)
        if abs(angle) < 0.5:
            return img  # No meaningful skew

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, scale=1.0)
        deskewed = cv2.warpAffine(
            img, rotation_matrix, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        logger.debug("Deskewed image by %.2f degrees", angle)
        return deskewed

    @staticmethod
    def binarize(gray: np.ndarray) -> np.ndarray:
        """
        Apply Otsu's binarization to improve OCR on low-contrast images.

        Also applies a 3x3 Gaussian blur before thresholding to reduce noise.
        """
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    @staticmethod
    def denoise(binary: np.ndarray) -> np.ndarray:
        """
        Remove small noise blobs using morphological opening.

        A 2x2 kernel is used to preserve small Devanagari marks (matras).
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        return opened

    @classmethod
    def preprocess(cls, pil_img: Image.Image) -> Image.Image:
        """
        Full preprocessing pipeline: deskew → grayscale → binarize → denoise.

        Returns a PIL Image ready for PaddleOCR.
        """
        cv2_img = cls.pil_to_cv2(pil_img)
        deskewed = cls.deskew(cv2_img)
        gray = cls.to_gray(deskewed)
        binary = cls.binarize(gray)
        denoised = cls.denoise(binary)
        # Convert back to RGB PIL (PaddleOCR expects RGB)
        rgb = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
        return Image.fromarray(rgb)


# ---------------------------------------------------------------------------
# TextExtractor — main class
# ---------------------------------------------------------------------------

class TextExtractor:
    """
    Extracts text from PDFs using PyMuPDF with PaddleOCR fallback.

    Parameters
    ----------
    lang : str
        PaddleOCR language code. 'hi' for Hindi/Devanagari (covers Sanskrit).
        'en' for English only. PaddleOCR supports multilingual detection.
    dpi : int
        Resolution for rendering PDF pages to images for OCR (default 200).
        Higher DPI → better OCR → slower processing.
    min_text_per_page : int
        If average chars/page from PyMuPDF < this value, fall back to OCR.
    ocr_batch_size : int
        Number of pages to send to PaddleOCR in one batch call.
    """

    def __init__(
        self,
        lang: str = "hi",
        dpi: int = 200,
        min_text_per_page: int = 100,
        ocr_batch_size: int = 4,
    ) -> None:
        self.lang = lang
        self.dpi = dpi
        self.min_text_per_page = min_text_per_page
        self.ocr_batch_size = ocr_batch_size
        self._ocr_engine: Optional[Any] = None   # Lazy-loaded PaddleOCR instance
        self._preprocessor = ImagePreprocessor()

    # ------------------------------------------------------------------
    # PaddleOCR lazy initialisation
    # ------------------------------------------------------------------

    def _get_ocr_engine(self) -> Any:
        """
        Lazily initialise PaddleOCR (slow first import).

        Using use_angle_cls=True helps with rotated/mixed text.
        use_gpu=False ensures CPU compatibility on machines without CUDA.
        """
        if self._ocr_engine is None:
            logger.info("Initialising PaddleOCR (lang=%s) — first call may be slow…", self.lang)
            try:
                from paddleocr import PaddleOCR  # type: ignore
                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.lang,
                    use_gpu=False,
                    show_log=False,
                    enable_mkldnn=True,  # Intel MKL-DNN acceleration
                )
                logger.info("PaddleOCR initialised successfully")
            except ImportError:
                raise RuntimeError(
                    "PaddleOCR is not installed. "
                    "Run: pip install paddleocr paddlepaddle"
                )
        return self._ocr_engine

    # ------------------------------------------------------------------
    # PyMuPDF extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pymupdf(doc: fitz.Document) -> List[PageResult]:
        """
        Extract text from all pages using PyMuPDF.

        PyMuPDF returns text in reading order with layout preservation.
        We use 'text' mode (no HTML/JSON overhead).
        """
        results: List[PageResult] = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")  # Plain text, preserves layout
            # Normalise whitespace
            text = "\n".join(
                line.strip() for line in text.splitlines() if line.strip()
            )
            results.append(PageResult(
                page_num=i,
                text=text,
                confidence=1.0,  # No OCR confidence needed for text-layer
                method="pymupdf",
            ))
        return results

    # ------------------------------------------------------------------
    # PaddleOCR extraction
    # ------------------------------------------------------------------

    def _page_to_image(self, page: fitz.Page) -> Image.Image:
        """Render a fitz page to a PIL Image at the configured DPI."""
        scale = self.dpi / 72.0  # fitz default is 72 DPI
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def _run_ocr_on_image(self, pil_img: Image.Image) -> Tuple[str, float]:
        """
        Run PaddleOCR on a single PIL Image.

        Returns
        -------
        text : str
            Extracted text lines joined by newline.
        confidence : float
            Mean confidence across all detected text boxes.
        """
        preprocessed = self._preprocessor.preprocess(pil_img)
        img_array = np.array(preprocessed)

        ocr = self._get_ocr_engine()
        result = ocr.ocr(img_array, cls=True)

        if not result or not result[0]:
            return "", 0.0

        lines: List[str] = []
        confidences: List[float] = []

        for line in result[0]:
            if line is None:
                continue
            # PaddleOCR returns: [[box_coords], (text, confidence)]
            text_conf = line[1]
            if text_conf and len(text_conf) >= 2:
                txt, conf = text_conf[0], text_conf[1]
                if txt and txt.strip():
                    lines.append(txt.strip())
                    confidences.append(float(conf))

        combined_text = "\n".join(lines)
        mean_confidence = float(np.mean(confidences)) if confidences else 0.0
        return combined_text, mean_confidence

    def _extract_paddleocr(self, doc: fitz.Document) -> List[PageResult]:
        """OCR-extract all pages from a fitz Document."""
        results: List[PageResult] = []
        total_pages = len(doc)
        logger.info("Running PaddleOCR on %d pages…", total_pages)

        for i, page in enumerate(doc, start=1):
            logger.debug("OCR page %d/%d", i, total_pages)
            pil_img = self._page_to_image(page)
            text, confidence = self._run_ocr_on_image(pil_img)
            results.append(PageResult(
                page_num=i,
                text=text,
                confidence=confidence,
                method="paddleocr",
            ))
        return results

    # ------------------------------------------------------------------
    # Decision logic: PyMuPDF vs OCR
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_chars_per_page(page_results: List[PageResult]) -> float:
        """Compute average character count per page."""
        if not page_results:
            return 0.0
        total_chars = sum(len(p.text) for p in page_results)
        return total_chars / len(page_results)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_pdf(self, pdf_path: Path) -> PDFResult:
        """
        Extract text from a single PDF file.

        Strategy:
        1. Extract using PyMuPDF.
        2. If avg chars/page < min_text_per_page → re-extract with PaddleOCR.
        3. For hybrid PDFs (some pages text, some scanned), we can mix methods
           in future — for now we apply one method to all pages.

        Parameters
        ----------
        pdf_path : Path
            Absolute or relative path to the PDF file.

        Returns
        -------
        PDFResult
            Complete extraction result with page-by-page data.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info("Extracting: %s", pdf_path.name)
        t_start = time.monotonic()

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        # Step 1: Try PyMuPDF
        pymupdf_pages = self._extract_pymupdf(doc)
        avg_chars = self._avg_chars_per_page(pymupdf_pages)
        logger.debug("PyMuPDF avg chars/page: %.1f (threshold: %d)", avg_chars, self.min_text_per_page)

        if avg_chars >= self.min_text_per_page:
            # Text-layer PDF — PyMuPDF is sufficient
            method = "pymupdf"
            pages = pymupdf_pages
        else:
            # Scanned PDF — fall back to PaddleOCR
            logger.info(
                "Low text yield (%.0f chars/page) → switching to PaddleOCR OCR",
                avg_chars,
            )
            method = "paddleocr"
            pages = self._extract_paddleocr(doc)

        doc.close()

        # Build page dict (1-indexed string keys for JSON)
        pages_dict: Dict[str, PageResult] = {
            str(p.page_num): p for p in pages
        }

        elapsed = time.monotonic() - t_start
        logger.info(
            "Extracted %d pages from '%s' in %.1fs (method=%s)",
            total_pages, pdf_path.name, elapsed, method,
        )

        return PDFResult(
            source_file=pdf_path.name,
            source_path=str(pdf_path.resolve()),
            total_pages=total_pages,
            extraction_method=method,
            pages=pages_dict,
            extraction_time_sec=elapsed,
        )

    def save_result(self, result: PDFResult, output_path: Path) -> None:
        """Serialise a PDFResult to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.debug("Saved extraction result to %s", output_path)

    def extract_all(
        self,
        input_dir: Path,
        output_dir: Path,
        overwrite: bool = False,
    ) -> List[Path]:
        """
        Batch-extract all PDFs found recursively under ``input_dir``.

        Already-processed files are skipped unless ``overwrite=True``.

        Parameters
        ----------
        input_dir : Path
            Root directory containing PDF files (may be nested by purana).
        output_dir : Path
            Root directory for JSON output files.
        overwrite : bool
            Re-process already-extracted files.

        Returns
        -------
        list[Path]
            Paths of all written JSON output files.
        """
        pdf_files = sorted(input_dir.rglob("*.pdf"))
        if not pdf_files:
            logger.warning("No PDF files found under %s", input_dir)
            return []

        logger.info("Found %d PDF file(s) to extract", len(pdf_files))
        output_paths: List[Path] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            overall = progress.add_task("Extracting PDFs…", total=len(pdf_files))

            for pdf_path in pdf_files:
                # Compute output path: mirror input dir structure
                try:
                    relative = pdf_path.relative_to(input_dir)
                except ValueError:
                    relative = Path(pdf_path.name)

                out_path = (output_dir / relative).with_suffix(".json")

                if out_path.exists() and not overwrite:
                    logger.debug("Skipping (already extracted): %s", pdf_path.name)
                    output_paths.append(out_path)
                    progress.advance(overall)
                    continue

                progress.update(overall, description=f"Extracting [cyan]{pdf_path.name}[/cyan]")
                try:
                    result = self.extract_pdf(pdf_path)
                    self.save_result(result, out_path)
                    output_paths.append(out_path)
                except Exception as exc:
                    logger.error("Failed to extract '%s': %s", pdf_path.name, exc, exc_info=True)
                finally:
                    progress.advance(overall)

        console.print(
            f"[green]Extraction complete.[/green] "
            f"Processed [bold]{len(output_paths)}[/bold] file(s) → [cyan]{output_dir}[/cyan]"
        )
        return output_paths


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI wrapper around TextExtractor for batch processing."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="purangpt-extractor",
        description="Extract text from Puranic PDF files",
    )
    parser.add_argument(
        "input", nargs="?", default="data/raw_pdfs",
        help="Input directory or single PDF file (default: data/raw_pdfs)",
    )
    parser.add_argument(
        "--output-dir", default="data/extracted",
        help="Output directory for JSON files (default: data/extracted)",
    )
    parser.add_argument(
        "--lang", default="hi",
        help="PaddleOCR language code (default: hi for Hindi/Devanagari)",
    )
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="DPI for page rendering during OCR (default: 200)",
    )
    parser.add_argument(
        "--min-text", type=int, default=100,
        help="Minimum avg chars/page before switching to OCR (default: 100)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Re-process already-extracted files",
    )
    args = parser.parse_args()

    extractor = TextExtractor(
        lang=args.lang,
        dpi=args.dpi,
        min_text_per_page=args.min_text,
    )

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        # Single file mode
        result = extractor.extract_pdf(input_path)
        out = (output_dir / input_path.stem).with_suffix(".json")
        extractor.save_result(result, out)
        console.print(f"[green]Saved:[/green] {out}")
    else:
        # Batch mode
        extractor.extract_all(input_path, output_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
