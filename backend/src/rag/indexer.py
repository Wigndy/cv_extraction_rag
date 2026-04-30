"""Indexing utilities for base datasets and uploaded resumes."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag.db_client import ChromaResumeStore


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class ResumeIndexer:
	"""Chunk and upsert resume text into ChromaDB with metadata filters."""

	chunk_size: int
	chunk_overlap: int
	store: ChromaResumeStore

	@classmethod
	def from_config(cls) -> "ResumeIndexer":
		"""Instantiate indexer using configured chunking and vector store values."""
		config = _load_config()
		rag = config.get("rag", {})
		return cls(
			chunk_size=int(rag.get("chunk_size", 800)),
			chunk_overlap=int(rag.get("chunk_overlap", 120)),
			store=ChromaResumeStore.from_config(),
		)

	def index_base_data(self) -> int:
		"""Index processed HR and IT datasets as base documents.

		Returns:
			Number of inserted chunks.
		"""
		config = _load_config()
		root = Path(__file__).resolve().parents[2]
		paths = config.get("paths", {})
		hr_path = root / paths.get("processed_hr_json", "data/processed/hr_extracted_data.json")
		it_path = root / paths.get("processed_it_json", "data/processed/it_extracted_data.json")

		records: list[dict[str, Any]] = []
		records.extend(self._load_records(hr_path, "HR"))
		records.extend(self._load_records(it_path, "INFORMATION-TECHNOLOGY"))
		return self._upsert_records(records, is_base_data=True)

	def index_uploaded_resume(self, text: str, source_file: str, session_id: str) -> int:
		"""Index uploaded resume into collection with session metadata.

		Args:
			text: Resume text extracted by ingestion stage.
			source_file: Original file name.
			session_id: UI session identifier for retrieval filtering.

		Returns:
			Number of inserted chunks.
		"""
		record = {
			"text": text,
			"metadata": {
				"source_file": source_file,
				"session_id": session_id,
				"is_base_data": False,
			},
		}
		return self._upsert_records([record], is_base_data=False)

	def upsert_chunks(self, chunks: list[dict[str, Any]], default_department: str = None) -> int:
		"""Upsert pre-computed semantic chunks into appropriate ChromaDB collection."""
		if not chunks:
			return 0

		collections_data = {}
		
		for index, chunk in enumerate(chunks):
			text = str(chunk.get("text", "")).strip()
			if not text:
				continue
			
			raw_metadata = chunk.get("metadata", {})
			dept = raw_metadata.get("department", default_department) or "unknown"
			chunk_type = raw_metadata.get("chunk_type", "misc")
			source_file = raw_metadata.get("source_file", "unknown")
			
			clean_metadata = {
				"department": dept.lower(),
				"chunk_type": chunk_type,
				"source_file": source_file
			}
				
			coll_name = f"{dept.lower()}_collection"
			
			if coll_name not in collections_data:
				collections_data[coll_name] = {"ids": [], "docs": [], "metadatas": []}
				
			hash_id = hashlib.md5(f"{source_file}_{chunk_type}_{index}".encode()).hexdigest()
			
			collections_data[coll_name]["ids"].append(f"id_{hash_id}")
			collections_data[coll_name]["docs"].append(text)
			collections_data[coll_name]["metadatas"].append(clean_metadata)
			
		total_inserted = 0
		for coll_name, data in collections_data.items():
			if not data["ids"]:
				continue
				
			target_collection = self.store.get_collection(collection_name=coll_name)
			
			target_collection.upsert(
				ids=data["ids"],
				documents=data["docs"],
				metadatas=data["metadatas"]
			)
			total_inserted += len(data["ids"])
			
		return total_inserted

	def _load_records(self, path: Path, department: str) -> list[dict[str, Any]]:
		"""Load parsed records from disk and normalize minimal index payload."""
		if not path.exists():
			return []
		try:
			rows = json.loads(path.read_text(encoding="utf-8") or "[]")
		except json.JSONDecodeError:
			return []

		normalized: list[dict[str, Any]] = []
		for row in rows:
			text = row.get("text", "")
			metadata = row.get("metadata", {})
			metadata["department"] = metadata.get("department", department)
			normalized.append({"text": text, "metadata": metadata})
		return normalized

	def _upsert_records(self, records: list[dict[str, Any]], is_base_data: bool) -> int:
		"""Split text into chunks and upsert with deterministic metadata."""
		if not records:
			return 0

		splitter = RecursiveCharacterTextSplitter(
			chunk_size=self.chunk_size,
			chunk_overlap=self.chunk_overlap,
		)
		collection = self.store.get_collection()

		ids: list[str] = []
		docs: list[str] = []
		metadatas: list[dict[str, Any]] = []

		for record in records:
			text = str(record.get("text", "")).strip()
			if not text:
				continue
			metadata = dict(record.get("metadata", {}))
			metadata["is_base_data"] = is_base_data

			chunks = splitter.split_text(text)
			for index, chunk in enumerate(chunks):
				ids.append(f"chunk-{uuid.uuid4()}-{index}")
				docs.append(chunk)
				metadatas.append(metadata)

		if not ids:
			return 0

		collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
		return len(ids)
