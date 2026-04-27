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

3. Configure local backend URL:

```bash
export OLLAMA_BASE_URL="http://host.docker.internal:11434"
```

## Hybrid Local Architecture (Docker App + Host Ollama)
The Streamlit app runs in Docker, while Ollama runs natively on macOS host.

### 1. Prepare host backend
1. Start Ollama app on macOS and ensure service is running.
2. Pull required models:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

3. Install system libraries on host:

```bash
brew install tesseract poppler
```

### 2. Docker-to-host bridge
The app container uses:
- OLLAMA_BASE_URL=http://host.docker.internal:11434

UI port remains exposed:
- 8501:8501

### 3. Manual run sequence
1. Start Ollama on host.
2. Start app containers:

```bash
docker compose up --build
```

3. Open browser at http://localhost:8501

The UI performs backend health check. If Ollama is down, app shows not connected state.
When Ollama is back up, click Refresh Backend Status or reload page.

### 4. Optional automation
1. Enable Ollama auto-start at login.
2. Create startup script to open Docker Desktop and run docker compose up.
3. Add startup script to macOS Login Items.

### 5. Monitoring and shutdown
1. Check logs:

```bash
docker compose logs -f resume-rag-app
```

2. Before shutdown:

```bash
docker compose down
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
