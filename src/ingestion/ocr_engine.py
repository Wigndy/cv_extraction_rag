"""OCR engine module for extracting text from scanned PDF pages.

This module renders PDF pages as images with PyMuPDF and applies Tesseract OCR
to extract text when no text layer is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


@dataclass(slots=True)
class PDFOCREngine:
	"""OCR processor for scanned resume PDFs.

	Attributes:
		language: Tesseract language code.
		dpi: Target rendering DPI to improve OCR quality.
	"""

	language: str = "eng"
	dpi: int = 300

	def extract_text(self, pdf_path: str | Path) -> str:
		"""Extract text from a scanned PDF using image-based OCR.

		Args:
			pdf_path: Absolute or relative path to the PDF file.

		Returns:
			OCR text aggregated from all pages.
		"""
		path = Path(pdf_path)
		page_texts: list[str] = []
		scale = self.dpi / 72.0
		matrix = fitz.Matrix(scale, scale)

		with fitz.open(path) as document:
			for page in document:
				pixmap = page.get_pixmap(matrix=matrix, alpha=False)
				mode = "RGB"
				image = Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)
				text = pytesseract.image_to_string(image, lang=self.language).strip()
				if text:
					page_texts.append(text)

		return "\n\n".join(page_texts).strip()
