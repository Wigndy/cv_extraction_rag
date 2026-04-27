"""LLM client module for schema-constrained extraction calls.

This service converts raw resume text into validated Pydantic objects and
persists records into department-specific JSON files.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_ollama import ChatOllama
from pydantic import ValidationError
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

	max_retries: int
	retry_wait_seconds: int
	processed_hr_path: Path
	processed_it_path: Path
	ollama_base_url: str
	model_name: str
	temperature: float

	@classmethod
	def from_config(cls) -> "ResumeLLMExtractor":
		"""Build service from YAML configuration values."""
		config = _load_config()
		extraction = config.get("extraction", {})
		paths = config.get("paths", {})
		root = Path(__file__).resolve().parents[2]

		return cls(
			max_retries=int(extraction.get("max_retries", 3)),
			retry_wait_seconds=int(extraction.get("retry_wait_seconds", 2)),
			processed_hr_path=root / paths.get("processed_hr_json", "data/processed/hr_extracted_data.json"),
			processed_it_path=root / paths.get("processed_it_json", "data/processed/it_extracted_data.json"),
			ollama_base_url=os.getenv(extraction.get("base_url_env", "OLLAMA_BASE_URL"), "http://host.docker.internal:11434"),
			model_name=extraction.get("model_name", "qwen2.5:7b"),
			temperature=float(extraction.get("temperature", 0.0)),
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

	def _chat_model(self) -> ChatOllama:
		"""Create a ChatOllama instance for extraction requests."""
		return ChatOllama(
			model=self.model_name,
			base_url=self.ollama_base_url,
			temperature=self.temperature,
			format="json",
		)

	def _extract_with_retry(self, text: str) -> ResumeExtraction:
		"""Call Ollama and enforce strict schema parsing with repair fallback."""
		prompt = build_user_prompt(text)
		parser = PydanticOutputParser(pydantic_object=ResumeExtraction)
		fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self._chat_model())
		full_prompt = (
			f"{prompt}\n\n"
			"Return only valid JSON.\n"
			f"{parser.get_format_instructions()}"
		)

		retrying = Retrying(
			stop=stop_after_attempt(self.max_retries),
			wait=wait_fixed(self.retry_wait_seconds),
			reraise=True,
		)

		for attempt in retrying:
			with attempt:
				response = self._chat_model().invoke(
					[
						("system", SYSTEM_PROMPT),
						("human", full_prompt),
					]
				)
				raw = response.content if hasattr(response, "content") else str(response)

				try:
					if isinstance(raw, list):
						raw = "".join([str(part) for part in raw])
					return ResumeExtraction.model_validate_json(raw)
				except (ValidationError, json.JSONDecodeError, TypeError):
					fixed = fixing_parser.parse(raw)
					if isinstance(fixed, ResumeExtraction):
						return fixed
					if isinstance(fixed, dict):
						return ResumeExtraction.model_validate(fixed)
					if isinstance(fixed, str):
						return ResumeExtraction.model_validate_json(fixed)
					raise ValueError("Could not parse model output into ResumeExtraction")

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
