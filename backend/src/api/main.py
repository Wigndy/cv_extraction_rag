from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import tempfile
import uuid
import os
from pathlib import Path
import chromadb
from contextlib import asynccontextmanager

from src.extraction.processor import ResumeExtractor
from src.ingestion.router import ResumeIngestionRouter
from src.rag.indexer import ResumeIndexer
from src.rag.retriever import ResumeRetriever

# Initialize components globally
ingestion_router = ResumeIngestionRouter.from_config()
extractor = ResumeExtractor()
indexer = ResumeIndexer.from_config()
retriever = ResumeRetriever.from_config()

def cleanup_orphan_collections():
    """Hàm dọn dẹp tất cả các collection rác (bắt đầu bằng temp_cv_)"""
    try:
        client = chromadb.PersistentClient(path=str(indexer.store.persist_path))
        collections = client.list_collections()
        for c in collections:
            if c.name.startswith("temp_cv_"):
                try:
                    client.delete_collection(name=c.name)
                    print(f"✅ Đã dọn dẹp rác: {c.name}")
                except Exception as e:
                    print(f"❌ Lỗi khi xóa {c.name}: {e}")
    except Exception as e:
        print(f"❌ Lỗi kết nối ChromaDB khi dọn rác: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chạy khi FastAPI khởi động
    print("🚀 Đang khởi động FastAPI: Bắt đầu dọn dẹp rác dữ liệu cũ...")
    cleanup_orphan_collections()
    yield
    # Chạy khi FastAPI tắt
    print("🛑 Đang tắt FastAPI...")

app = FastAPI(title="Resume RAG API", lifespan=lifespan)



class QueryRequest(BaseModel):
    query: str
    department: str | None = None
    session_id: str | None = None
    context_mode: str = "Department Base Data"

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/upload")
async def upload_resume(
    file: UploadFile = File(...),
    department: str = Form(...),
    extraction_mode: str = Form("Auto"),
    session_id: str = Form(...)
):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        payload = ingestion_router.ingest(tmp_path, department=department, extraction_mode=extraction_mode)
        
        metadata = payload["metadata"]
        metadata["source_file"] = file.filename
        
        digital_text = payload["digital_text"]
        visual_text = payload["visual_text"]
        
        # Reconstruct combined text for indexing
        if digital_text and visual_text:
            combined_text = f"--- DIGITAL TEXT ---\n{digital_text}\n--- OCR SUPPLEMENTARY DATA ---\n{visual_text}"
        elif digital_text:
            combined_text = digital_text
        else:
            combined_text = visual_text or ""

        # Extract structured data
        extracted_data = extractor.extract(digital_text=digital_text, visual_text=visual_text)
        extracted_dict = extracted_data.model_dump(mode='json') if hasattr(extracted_data, 'model_dump') else extracted_data
        
        # Build record for chunker
        record = {
            "metadata": {
                "source_file": file.filename,
                "department": f"temp_cv_{session_id}",
                "session_id": session_id
            },
            "extracted": extracted_dict
        }
        
        # Generate semantic chunks
        from src.rag.chunker import ResumeChunker
        chunker = ResumeChunker()
        chunks = chunker.create_semantic_chunks(record)
        
        # Add session_id to chunks metadata for later retrieval
        for chunk in chunks:
            chunk["metadata"]["session_id"] = session_id
            
        # Upsert into temp_session_collection
        indexed_chunks = indexer.upsert_chunks(chunks)
        os.unlink(tmp_path)
        return {
            "message": "Success",
            "session_id": session_id,
            "indexed_chunks": indexed_chunks,
            "filename": file.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/index_base")
def index_base():
    try:
        chunk_count = indexer.index_base_data()
        return {"chunk_count": chunk_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query")
def query(req: QueryRequest):
    try:
        if req.context_mode == "Uploaded Session Data" and req.session_id:
            result = retriever.retrieve(query=req.query, session_id=req.session_id)
        else:
            result = retriever.retrieve(query=req.query, department=req.department)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    """Xóa collection tạm thời khi người dùng kết thúc phiên."""
    try:
        coll_name = f"temp_cv_{session_id}_collection"
        client = chromadb.PersistentClient(path=str(indexer.store.persist_path))
        try:
            client.delete_collection(name=coll_name)
            return {"message": f"Deleted collection {coll_name}"}
        except ValueError:
            return {"message": f"Collection {coll_name} does not exist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/collections")
def list_collections():
    """Liệt kê toàn bộ các collection đang tồn tại trong ChromaDB."""
    try:
        client = chromadb.PersistentClient(path=str(indexer.store.persist_path))
        collections = client.list_collections()
        result = [{"name": c.name, "count": c.count()} for c in collections]
        return {"collections": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
