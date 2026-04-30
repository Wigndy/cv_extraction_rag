"""Routing logic for PDF text extraction.

The router detects whether a PDF has a text layer and dispatches extraction to
either a direct text parser or OCR engine.
"""

from __future__ import annotations

import re
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


def clean_text(text: str) -> str:
	"""Encoding & Cleanup: fix artifacts, normalize whitespace, remove empty lines."""
	if not text:
		return ""
	# Fix common artifacts
	text = text.replace("â€", "•")
	# Normalize whitespaces and remove empty lines
	lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
	return "\n".join(line for line in lines if line)


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

	def ingest(self, pdf_path: str | Path, department: str | None = None, extraction_mode: str = "Auto") -> dict[str, Any]:
		"""Extract text and return unified output payload.

		Args:
			pdf_path: Path to the resume PDF.
			department: Optional explicit department label.
			extraction_mode: Strategy for external/uploaded files (Auto, Digital Only, Forced OCR).

		Returns:
			A dictionary with keys: digital_text, visual_text, combined_text, metadata
		"""
		path = Path(pdf_path)
		detected_department = department or self._infer_department(path)
		
		# Data Source Detection
		is_internal = "data/raw" in path.absolute().as_posix() or "data/raw" in path.as_posix()
		source = "internal" if is_internal else "external"

		digital_text = None
		visual_text = None
		method_used = []

		if source == "internal":
			# Scenario A (Internal Data): Execute BOTH sequentially
			raw_digital = self.text_parser.extract_text(path)
			raw_visual = self.ocr_engine.extract_text(path)
			
			digital_text = clean_text(raw_digital) if raw_digital else None
			visual_text = clean_text(raw_visual) if raw_visual else None
			method_used = ["text", "ocr"]
		else:
			# Scenario B (External Data): Use extraction_mode
			if extraction_mode == "Digital Only":
				raw_digital = self.text_parser.extract_text(path)
				digital_text = clean_text(raw_digital) if raw_digital else None
				method_used = ["text"]
			elif extraction_mode == "Forced OCR":
				raw_visual = self.ocr_engine.extract_text(path)
				visual_text = clean_text(raw_visual) if raw_visual else None
				method_used = ["ocr"]
			else: # Auto
				if self.text_parser.has_text_layer(path):
					raw_digital = self.text_parser.extract_text(path)
					digital_text = clean_text(raw_digital) if raw_digital else None
					if not digital_text or len(digital_text) < 100: # Threshold-based OCR fallback
						raw_visual = self.ocr_engine.extract_text(path)
						visual_text = clean_text(raw_visual) if raw_visual else None
						method_used = ["ocr"]
					else:
						method_used = ["text"]
				else:
					raw_visual = self.ocr_engine.extract_text(path)
					visual_text = clean_text(raw_visual) if raw_visual else None
					method_used = ["ocr"]

		return {
			"digital_text": digital_text,
			"visual_text": visual_text,
			"metadata": {
				"source": source,
				"method_used": method_used,
				"extraction_mode": extraction_mode if source == "external" else "Internal Batch",
				"department": detected_department,
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
