"""PDF parser module for extracting text layers from digital PDFs.

This module uses PyMuPDF to detect whether a PDF has an accessible text layer
and to extract normalized text when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(slots=True)
class PDFTextParser:
	"""Extract text content from text-based PDF files.

	The parser performs two operations:
	1. Detect if a document includes meaningful text in any page.
	2. Extract and normalize text from all pages.
	"""

	min_text_chars: int = 20

	def has_text_layer(self, pdf_path: str | Path) -> bool:
		"""Return True when at least one page contains sufficient text.

		Args:
			pdf_path: Absolute or relative path to the PDF file.

		Returns:
			True if a text layer is likely present, False otherwise.
		"""
		path = Path(pdf_path)
		with fitz.open(path) as document:
			for page in document:
				text = page.get_text("text").strip()
				if len(text) >= self.min_text_chars:
					return True
		return False

	def extract_text(self, pdf_path: str | Path) -> str:
		"""Extract full text from all pages and return normalized output.

		Args:
			pdf_path: Absolute or relative path to the PDF file.

		Returns:
			A single string containing page-joined text.
		"""
		path = Path(pdf_path)
		pages: list[str] = []
		with fitz.open(path) as document:
			for page in document:
				page_text = page.get_text("text").strip()
				if page_text:
					pages.append(page_text)
		return "\n\n".join(pages).strip()
