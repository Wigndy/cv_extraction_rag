# Resume Parser and RAG Chat System

## Overview
This project provides an end-to-end pipeline for resume processing:
1. Ingest text-based or scanned PDF resumes.
2. Extract structured entities with schema-constrained LLM output.
3. Persist base and session-specific vectors in ChromaDB.
4. Query data with metadata-aware retrieval in a Streamlit chat UI.
5. Evaluate retrieval-answer quality using RAGAS.

## Dataset Label Correction
This implementation uses the actual dataset labels and paths:
- HR
- INFORMATION-TECHNOLOGY

## Key Modules
- src/ingestion: PDF router, text parser, OCR engine.
- src/extraction: Pydantic schema, prompts, LLM extraction and persistence.
- src/rag: Persistent Chroma client, indexer, filtered retriever.
- src/ui: Streamlit application for upload and chat.
- src/evaluation: RAGAS metrics and evaluation runner.

## Environment Setup
1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set API keys:

```bash
export OPENAI_API_KEY="your_key"
```

## Run the Streamlit App
```bash
streamlit run src/ui/app.py
```

## Index Base Dataset
Use the Index Base Dataset button in the Streamlit sidebar after extraction files are populated.

## Evaluation
Smoke test first (recommended):

```bash
python -m src.evaluation.run_eval --smoke-size 3
```

Run full configured evaluation only after confirmation:

```bash
python -m src.evaluation.run_eval --confirm-large-run
```

Report output is written to data/processed/evaluation_report.json.

## Docker
Build and run with:

```bash
docker compose up --build
```
