"""LLM client module for schema-constrained extraction calls.

This service converts raw resume text into validated Pydantic objects and
persists records into department-specific JSON files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI
from tenacity import Retrying, stop_after_attempt, wait_fixed

from src.extraction.prompt import SYSTEM_PROMPT, build_user_prompt
from src.extraction.schema import ResumeExtraction, ResumeRecord


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class ResumeLLMExtractor:
	"""Schema-constrained LLM extraction and persistence service.

	The service uses LangChain structured output to map free text to the
	`ResumeExtraction` model and appends records to department-specific stores.
	"""

	model_name: str
	temperature: float
	timeout_seconds: int
	max_retries: int
	retry_wait_seconds: int
	processed_hr_path: Path
	processed_it_path: Path

	@classmethod
	def from_config(cls) -> "ResumeLLMExtractor":
		"""Build service from YAML configuration values."""
		config = _load_config()
		extraction = config.get("extraction", {})
		paths = config.get("paths", {})
		root = Path(__file__).resolve().parents[2]

		return cls(
			model_name=extraction.get("model_name", "gpt-4.1-mini"),
			temperature=float(extraction.get("temperature", 0.0)),
			timeout_seconds=int(extraction.get("timeout_seconds", 60)),
			max_retries=int(extraction.get("max_retries", 3)),
			retry_wait_seconds=int(extraction.get("retry_wait_seconds", 2)),
			processed_hr_path=root / paths.get("processed_hr_json", "data/processed/hr_extracted_data.json"),
			processed_it_path=root / paths.get("processed_it_json", "data/processed/it_extracted_data.json"),
		)

	def extract_and_persist(self, text: str, metadata: dict[str, str]) -> ResumeRecord:
		"""Extract structured entities and append to the corresponding JSON file.

		Args:
			text: Raw resume content.
			metadata: Source metadata including `department` and `source_file`.

		Returns:
			ResumeRecord containing original text, metadata, and parsed entities.
		"""
		extracted = self._extract_with_retry(text)
		record = ResumeRecord(text=text, metadata=metadata, extracted=extracted)
		self._append_record(record)
		return record

	def _chat_model(self) -> ChatOpenAI:
		"""Create a ChatOpenAI instance for extraction requests."""
		return ChatOpenAI(
			model=self.model_name,
			temperature=self.temperature,
			timeout=self.timeout_seconds,
		)

	def _extract_with_retry(self, text: str) -> ResumeExtraction:
		"""Call the LLM with schema-constrained output and retry on failure."""
		model = self._chat_model().with_structured_output(ResumeExtraction)
		prompt = build_user_prompt(text)

		retrying = Retrying(
			stop=stop_after_attempt(self.max_retries),
			wait=wait_fixed(self.retry_wait_seconds),
			reraise=True,
		)

		for attempt in retrying:
			with attempt:
				return model.invoke(
					[
						("system", SYSTEM_PROMPT),
						("human", prompt),
					]
				)

		raise RuntimeError("Extraction failed after retries")

	def _append_record(self, record: ResumeRecord) -> None:
		"""Append record to HR or IT processed JSON output file."""
		department = record.metadata.get("department", "").upper()
		if department == "HR":
			target = self.processed_hr_path
		elif department == "INFORMATION-TECHNOLOGY":
			target = self.processed_it_path
		else:
			raise ValueError("Unsupported department label for persistence")

		target.parent.mkdir(parents=True, exist_ok=True)
		if not target.exists():
			target.write_text("[]\n", encoding="utf-8")

		existing = json.loads(target.read_text(encoding="utf-8") or "[]")
		existing.append(record.model_dump(by_alias=True))
		target.write_text(json.dumps(existing, indent=2, ensure_ascii=True), encoding="utf-8")
