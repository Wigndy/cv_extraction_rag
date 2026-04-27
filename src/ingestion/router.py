"""Routing logic for PDF text extraction.

The router detects whether a PDF has a text layer and dispatches extraction to
either a direct text parser or OCR engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.ingestion.ocr_engine import PDFOCREngine
from src.ingestion.pdf_parser import PDFTextParser


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class ResumeIngestionRouter:
	"""Route a PDF to the appropriate extraction strategy.

	The result format is standardized to support downstream extraction and
	indexing stages.
	"""

	text_parser: PDFTextParser
	ocr_engine: PDFOCREngine

	@classmethod
	def from_config(cls) -> "ResumeIngestionRouter":
		"""Create a router instance configured by project YAML settings."""
		config = _load_config()
		ocr_config = config.get("ingestion", {}).get("ocr", {})
		return cls(
			text_parser=PDFTextParser(),
			ocr_engine=PDFOCREngine(
				language=ocr_config.get("language", "eng"),
				dpi=int(ocr_config.get("dpi", 300)),
			),
		)

	def ingest(self, pdf_path: str | Path, department: str | None = None) -> dict[str, Any]:
		"""Extract text and return standardized output payload.

		Args:
			pdf_path: Path to the resume PDF.
			department: Optional explicit department label.

		Returns:
			A dictionary with keys:
			- text: extracted text content
			- metadata: source file, department, and extraction method
		"""
		path = Path(pdf_path)
		detected_department = department or self._infer_department(path)

		if self.text_parser.has_text_layer(path):
			text = self.text_parser.extract_text(path)
			method = "text"
		else:
			text = self.ocr_engine.extract_text(path)
			method = "ocr"

		return {
			"text": text,
			"metadata": {
				"source_file": path.name,
				"department": detected_department,
				"ingestion_method": method,
			},
		}

	@staticmethod
	def _infer_department(pdf_path: Path) -> str:
		"""Infer department from folder structure, falling back to UNKNOWN."""
		normalized_parts = [part.upper() for part in pdf_path.parts]
		if "HR" in normalized_parts:
			return "HR"
		if "INFORMATION-TECHNOLOGY" in normalized_parts:
			return "INFORMATION-TECHNOLOGY"
		return "UNKNOWN"
