"""ChromaDB client initialization and collection management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import yaml
from sentence_transformers import SentenceTransformer


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class EmbeddingFunctionAdapter:
	"""Adapter exposing SentenceTransformer embeddings to ChromaDB."""

	model_name: str

	def __post_init__(self) -> None:
		self._model = SentenceTransformer(self.model_name)

	def __call__(self, input: list[str]) -> list[list[float]]:
		"""Return vector embeddings for the provided documents."""
		vectors = self._model.encode(input, normalize_embeddings=True)
		return [vector.tolist() for vector in vectors]


@dataclass(slots=True)
class ChromaResumeStore:
	"""Persistent ChromaDB wrapper used by indexing and retrieval layers."""

	persist_path: Path
	collection_name: str
	embedding_model_name: str

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
			embedding_model_name=rag_config.get("embedding_model_name", "BAAI/bge-small-en-v1.5"),
		)

	def get_collection(self):
		"""Create or fetch persistent Chroma collection with embedding support."""
		self.persist_path.mkdir(parents=True, exist_ok=True)
		client = chromadb.PersistentClient(path=str(self.persist_path))
		embedding = EmbeddingFunctionAdapter(self.embedding_model_name)
		return client.get_or_create_collection(
			name=self.collection_name,
			embedding_function=embedding,
			metadata={"hnsw:space": "cosine"},
		)
