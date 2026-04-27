"""Streamlit app for resume upload, indexing, and RAG chat."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from src.extraction.llm_caller import ResumeLLMExtractor
from src.ingestion.router import ResumeIngestionRouter
from src.rag.indexer import ResumeIndexer
from src.rag.retriever import ResumeRetriever


def _load_config() -> dict[str, Any]:
	"""Load project configuration values from YAML."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


def _initialize_state() -> None:
	"""Initialize Streamlit session state keys."""
	if "messages" not in st.session_state:
		st.session_state.messages = []
	if "session_id" not in st.session_state:
		st.session_state.session_id = str(uuid.uuid4())
	if "uploaded_filename" not in st.session_state:
		st.session_state.uploaded_filename = ""
	if "last_upload_token" not in st.session_state:
		st.session_state.last_upload_token = ""


def main() -> None:
	"""Render and run the Streamlit application."""
	config = _load_config()
	_initialize_state()

	st.set_page_config(page_title="Resume Parser and RAG", layout="wide")
	st.title(config.get("ui", {}).get("title", "Resume Parser and RAG Chat"))

	ingestion_router = ResumeIngestionRouter.from_config()
	extractor = ResumeLLMExtractor.from_config()
	indexer = ResumeIndexer.from_config()
	retriever = ResumeRetriever.from_config()

	with st.sidebar:
		st.header("Controls")
		context_mode = st.radio(
			"Query Context",
			options=["Department Base Data", "Uploaded Session Data"],
			index=0,
		)

		department = st.selectbox(
			"Department",
			options=["HR", "INFORMATION-TECHNOLOGY"],
			index=0,
			disabled=context_mode != "Department Base Data",
		)

		uploaded_pdf = st.file_uploader("Upload Resume PDF", type=["pdf"])
		if uploaded_pdf is not None:
			upload_token = f"{uploaded_pdf.name}:{uploaded_pdf.size}"
			if upload_token != st.session_state.last_upload_token:
				with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
					temp_file.write(uploaded_pdf.read())
					temp_path = Path(temp_file.name)

				payload = ingestion_router.ingest(temp_path, department=department)
				st.session_state.uploaded_filename = uploaded_pdf.name
				st.session_state.session_id = str(uuid.uuid4())
				st.session_state.last_upload_token = upload_token

				metadata = payload["metadata"]
				metadata["source_file"] = uploaded_pdf.name

				extractor.extract_and_persist(text=payload["text"], metadata=metadata)
				indexed_chunks = indexer.index_uploaded_resume(
					text=payload["text"],
					source_file=uploaded_pdf.name,
					session_id=st.session_state.session_id,
				)
				st.success(
					f"Processed {uploaded_pdf.name} and indexed {indexed_chunks} chunks "
					f"for session {st.session_state.session_id}."
				)

		if st.button("Index Base Dataset"):
			chunk_count = indexer.index_base_data()
			st.success(f"Indexed {chunk_count} base chunks.")

	for message in st.session_state.messages:
		with st.chat_message(message["role"]):
			st.markdown(message["content"])

	question = st.chat_input("Ask a question about resumes...")
	if question:
		st.session_state.messages.append({"role": "user", "content": question})
		with st.chat_message("user"):
			st.markdown(question)

		with st.chat_message("assistant"):
			if context_mode == "Uploaded Session Data" and st.session_state.uploaded_filename:
				result = retriever.retrieve(
					query=question,
					session_id=st.session_state.session_id,
				)
			else:
				result = retriever.retrieve(
					query=question,
					department=department,
				)

			st.markdown(result["answer"])
			st.session_state.messages.append({"role": "assistant", "content": result["answer"]})


if __name__ == "__main__":
	main()
