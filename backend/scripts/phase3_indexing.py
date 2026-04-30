# python3 scripts/phase3_indexing.py --input data/processed/hr_extracted.json
# python3 scripts/phase3_indexing.py --input data/processed/it_extracted.json
import argparse
import sys
from pathlib import Path
import gc
import json

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.rag.indexer import ResumeIndexer
from src.rag.chunker import ResumeChunker
from src.storage_manager import setup_logger, log_memory_usage, load_json, save_json

logger = setup_logger("phase3_indexing")

def main():
    parser = argparse.ArgumentParser(description="Phase 3: Vector Indexing")
    parser.add_argument("--input", required=True, help="Input JSON file from Phase 2")
    parser.add_argument("--dept", required=False, help="Target department collection (e.g. hr, it)")
    args = parser.parse_args()
    
    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"Input file {input_file} does not exist.")
        sys.exit(1)
        
    records = load_json(input_file)
    if not records:
        logger.warning(f"No records found in {input_file}")
        return
        
    logger.info(f"Starting Phase 3. Loaded {len(records)} records.")
    
    chunks_dir = project_root / "data" / "chunks"
    
    # Initialize Persistent Indexer and Chunker
    indexer = ResumeIndexer.from_config()
    chunker = ResumeChunker()
    
    total_chunks = 0
    failed_log = []
    logs_dir = project_root / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    failed_files_path = logs_dir / "failed_files.txt"
    
    for i, record in enumerate(records):
        source_file = record.get("source_file") or record.get("metadata", {}).get("source_file", f"unknown_{i}")
        
        dept = args.dept or record.get("metadata", {}).get("department", "unknown").lower()
        dept_dir = chunks_dir / dept
        dept_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_file_path = dept_dir / f"{source_file}_chunks.json"
        
        if chunk_file_path.exists():
            logger.info(f"Skipping {source_file} (Already chunked in {dept})")
            continue
            
        logger.info(f"Indexing ({i+1}/{len(records)}): {source_file}")
        log_memory_usage(f"Phase3: Before {source_file}", logger)
        
        try:
            # Generate Semantic Chunks
            chunks = chunker.create_semantic_chunks(record)
            
            # Empty Check
            if not chunks or len(chunks) == 0:
                logger.warning(f"Content-less File: {source_file} generated 0 chunks.")
                failed_log.append(f"{source_file}: Content-less File (0 chunks)")
                continue
                
            # Save chunks to file for debugging
            save_json(chunks, chunk_file_path)
            
            # Upsert into ChromaDB
            chunks_inserted = indexer.upsert_chunks(chunks, default_department=dept)
            total_chunks += chunks_inserted
            logger.info(f"Inserted {chunks_inserted} chunks for {source_file}")
            
        except Exception as e:
            logger.error(f"Critical error on {source_file}: {str(e)}")
            failed_log.append(f"{source_file}: {str(e)}")
            
        # Optimization: Clear RAM
        gc.collect()
        log_memory_usage(f"Phase3: After {source_file}", logger)
        
    # Save log for later traceability
    if failed_log:
        with open(failed_files_path, "a", encoding="utf-8") as f:
            f.write("\n".join(failed_log) + "\n")
            
    logger.info(f"Phase 3 complete. Total {total_chunks} chunks inserted into Persistent Vector DB.")

if __name__ == "__main__":
    main()
