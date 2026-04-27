"""Retriever module with metadata-aware filtering for chat queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI

from src.rag.db_client import ChromaResumeStore


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class ResumeRetriever:
	"""Retrieve relevant chunks and generate grounded answers."""

	top_k: int
	answer_model_name: str
	store: ChromaResumeStore

	@classmethod
	def from_config(cls) -> "ResumeRetriever":
		"""Create retriever from YAML configuration."""
		config = _load_config()
		rag = config.get("rag", {})
		return cls(
			top_k=int(rag.get("top_k", 5)),
			answer_model_name=rag.get("answer_model_name", "gpt-4.1-mini"),
			store=ChromaResumeStore.from_config(),
		)

	def retrieve(self, query: str, department: str | None = None, session_id: str | None = None) -> dict[str, Any]:
		"""Retrieve documents from ChromaDB using metadata filtering.

		Exactly one of department or session_id should be provided.
		"""
		collection = self.store.get_collection()
		where = self._build_filter(department=department, session_id=session_id)

		results = collection.query(
			query_texts=[query],
			n_results=self.top_k,
			where=where,
		)

		documents = results.get("documents", [[]])[0]
		metadatas = results.get("metadatas", [[]])[0]
		answer = self._generate_answer(query=query, contexts=documents)

		return {
			"answer": answer,
			"contexts": documents,
			"metadatas": metadatas,
			"filter": where,
		}

	@staticmethod
	def _build_filter(department: str | None, session_id: str | None) -> dict[str, Any]:
		"""Create Chroma `where` filter for either base-data or session-data flow."""
		if session_id:
			return {"$and": [{"session_id": session_id}, {"is_base_data": False}]}
		if department:
			return {"$and": [{"department": department}, {"is_base_data": True}]}
		raise ValueError("Either department or session_id must be provided for retrieval")

	def _generate_answer(self, query: str, contexts: list[str]) -> str:
		"""Generate a concise answer grounded only on retrieved contexts."""
		context_block = "\n\n".join(contexts) if contexts else "No context found."
		model = ChatOpenAI(model=self.answer_model_name, temperature=0.0)
		prompt = (
			"You are a resume assistant. Use only the provided context to answer. "
			"If information is missing, explicitly say it is not available.\n\n"
			f"Question: {query}\n\n"
			f"Context:\n{context_block}"
		)
		response = model.invoke(prompt)
		return response.content if hasattr(response, "content") else str(response)
