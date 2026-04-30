# scripts/check_db_keys.py
import chromadb
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "data" / "vector_db"
client = chromadb.PersistentClient(path=str(db_path))

# Kiểm tra collection
coll = client.get_collection(name="hr_collection")
print(f"Total chunks in HR: {coll.count()}")

# Lấy thử 1 chunk để xem cấu trúc metadata
sample = coll.peek(limit=1)
print("\n--- Actual Metadata in Database ---")
print(sample['metadatas'][0])