"""ChromaDB client initialization and collection management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chromadb
from langchain_ollama import OllamaEmbeddings
import yaml


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class EmbeddingFunctionAdapter:
	"""Adapter exposing Ollama embeddings to ChromaDB."""

	model_name: str
	base_url: str
	_embedder: OllamaEmbeddings | None = field(default=None, init=False, repr=False)

	def __post_init__(self) -> None:
		self._ensure_embedder()

	def _ensure_embedder(self) -> None:
		"""Lazily initialize embedder to handle callback lifecycle safely."""
		if self._embedder is None:
			self._embedder = OllamaEmbeddings(
				model=self.model_name,
				base_url=self.base_url,
			)

	def __call__(self, input: list[str]) -> list[list[float]]:
		"""Return vector embeddings for the provided documents."""
		self._ensure_embedder()
		if self._embedder is None:
			raise RuntimeError("Ollama embedder initialization failed")
		return self._embedder.embed_documents(input)


@dataclass(slots=True)
class ChromaResumeStore:
	"""Persistent ChromaDB wrapper used by indexing and retrieval layers."""

	persist_path: Path
	collection_name: str
	embedding_model_name: str
	ollama_base_url: str

	@classmethod
	def from_config(cls) -> "ChromaResumeStore":
		"""Instantiate the store from YAML configuration."""
		config = _load_config()
		rag_config = config.get("rag", {})
		root = Path(__file__).resolve().parents[2]
		persist_dir = root / config.get("paths", {}).get("vector_db_dir", "data/vector_db")

		return cls(
			persist_path=persist_dir,
			collection_name=rag_config.get("collection_name", "resumes"),
			embedding_model_name=rag_config.get("embedding_model_name", "nomic-embed-text"),
			ollama_base_url=os.getenv(rag_config.get("base_url_env", "OLLAMA_BASE_URL"), "http://localhost:11434"),
		)

	def get_collection(self, collection_name: str = None):
		"""Create or fetch persistent Chroma collection with embedding support."""
		self.persist_path.mkdir(parents=True, exist_ok=True)
		client = chromadb.PersistentClient(
			path=str(self.persist_path),
			settings=chromadb.config.Settings(anonymized_telemetry=False)
		)
		embedding = EmbeddingFunctionAdapter(
			model_name=self.embedding_model_name,
			base_url=self.ollama_base_url,
		)
		target_name = collection_name or self.collection_name
		return client.get_or_create_collection(
			name=target_name,
			embedding_function=embedding,
			metadata={"hnsw:space": "cosine"},
		)
