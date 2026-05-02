"""Retriever module with metadata-aware filtering for chat queries."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from langchain_ollama import ChatOllama
import yaml
import regex as re
from src.rag.db_client import ChromaResumeStore


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


class ResumeRetriever:
	"""Retrieve relevant chunks and generate grounded answers."""

	def __init__(self, top_k: int, answer_model_name: str, ollama_base_url: str, store: ChromaResumeStore):
		self.top_k = top_k
		self.store = store
		# Khởi tạo model một lần duy nhất tại đây
		self.llm = ChatOllama(
			model=answer_model_name,
			base_url=ollama_base_url,
			temperature=0, # Giữ temperature = 0 để đảm bảo tính khách quan trong nghiên cứu
		)

	@classmethod
	def from_config(cls) -> "ResumeRetriever":
		"""Create retriever from YAML configuration."""
		config = _load_config()
		rag = config.get("rag", {})
		return cls(
			top_k=int(rag.get("top_k", 5)),
			answer_model_name=rag.get("answer_model_name", "qwen2.5:7b"),
			ollama_base_url=os.getenv(rag.get("base_url_env", "OLLAMA_BASE_URL"), "http://localhost:11434"),
			store=ChromaResumeStore.from_config(),
		)

	def retrieve(self, query: str, department: str = None, session_id: str = None) -> dict[str, Any]:
		"""Retrieve documents from ChromaDB and return answer with source coordinates."""
		if session_id:
			coll_name = f"temp_cv_{session_id}_collection"
			collection = self.store.get_collection(collection_name=coll_name)
			where_filter = None
		else:
			if not department:
				department = "hr"
			coll_name = f"{department.lower()}_collection"
			collection = self.store.get_collection(collection_name=coll_name)

			where_filter = {"department": department.lower()}

			file_match = re.search(r'(\d+\.pdf)', query)
			if file_match:
				target_file = file_match.group(1)
				where_filter = {
					"$and": [
						{"department": department.lower()},
						{"source_file": target_file}	
					]
				}

		query_params = {
			"query_texts": [query],
			"n_results": 5,
		}
		if where_filter:
			query_params["where"] = where_filter

		retrieved_chunks = collection.query(**query_params)
		documents = retrieved_chunks.get("documents", [[]])[0]
		metadatas = retrieved_chunks.get("metadatas", [[]])[0]
		
		if not documents:
			dept_name = department.upper() if department else "TẠM THỜI (Uploaded CV)"
			return {
				"answer": f"Không tìm thấy dữ liệu cho yêu cầu này trong hệ thống {dept_name}.",
				"source_coordinates": []
			}
		
		answer = self._generate_answer(query=query, contexts=documents)
		return {
			"answer": answer,
			"source_coordinates": [m.get('source_file') for m in metadatas],
		}

	def _generate_answer(self, query: str, contexts: list[str]) -> str:
		"""Generate a concise answer grounded only on retrieved contexts."""
		context_block = "\n\n".join(contexts) if contexts else "Không tìm thấy dữ liệu phù hợp."
		
		# Prompt ép LLM phải trích dẫn nguồn từ text chunk
		system_instruction = (
			"Bạn là trợ lý phân tích CV chuyên nghiệp. Nhiệm vụ của bạn là trả lời câu hỏi dựa trên ngữ cảnh.\n"
			"QUY TẮC BẮT BUỘC:\n"
			"1. Mỗi thông tin đưa ra PHẢI kèm theo tên file nguồn (ví dụ: 'Theo tài liệu 10694288.pdf, ứng viên có...')\n"
			"2. Chỉ sử dụng thông tin trong phần 'Context'. Nếu không có, hãy báo không tìm thấy.\n"
			"3. Không tự ý bịa đặt tên ứng viên nếu không có thông tin xác thực."
		)
		
		prompt = f"{system_instruction}\n\nQuestion: {query}\n\nContext:\n{context_block}"
		response = self.llm.invoke(prompt)
		return response.content if hasattr(response, "content") else str(response)
