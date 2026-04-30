# scripts/audit_indexing.py
import os
import chromadb
from pathlib import Path

def audit_database(dept_key="hr"):
    # 1. Kết nối DB
    db_path = Path("data/vector_db").resolve()
    client = chromadb.PersistentClient(path=str(db_path))
    coll_name = f"{dept_key.lower()}_collection"
    collection = client.get_collection(name=coll_name)

    # 2. Lấy danh sách source_file duy nhất trong DB
    results = collection.get(include=['metadatas'])
    indexed_files = set(m.get('source_file') for m in results['metadatas'] if m)

    # 3. Quét thư mục raw
    raw_dir = Path(f"data/raw/{dept_key.upper()}")
    raw_files = set(f.name for f in raw_dir.glob("*.pdf"))

    # 4. Đối soát
    missing_files = raw_files - indexed_files
    print(f"--- Audit Report for {dept_key.upper()} ---")
    print(f"Total Raw Files: {len(raw_files)}")
    print(f"Total Indexed: {len(indexed_files)}")
    print(f"Missing: {len(missing_files)}")
    if missing_files:
        print(f"List of missing: {list(missing_files)[:5]}...")
    
    return list(missing_files)

if __name__ == "__main__":
    audit_database("hr")
    audit_database("information-technology")
