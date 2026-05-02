import pandas as pd
import json
import asyncio
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Thư viện cho Mode 3 (API call bất đồng bộ)
import aiohttp

# Import RAG components
from src.rag.retriever import ResumeRetriever
from src.evaluation.metrics import calculate_hit_rate, LatencyTracker

class RAGEvaluator:
    def __init__(self):
        # Đường dẫn cơ bản
        self.data_path = Path("data/Resume.csv")
        self.logs_dir = Path("data/evaluation")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Khởi tạo Retriever (chỉ tạo khi cần để tránh block)
        self.retriever = None

    def _get_retriever(self):
        if self.retriever is None:
            self.retriever = ResumeRetriever.from_config()
        return self.retriever

    def _generate_query_from_text(self, text: str) -> str:
        """Tạo một query ngẫu nhiên từ text (lấy 1 đoạn dài khoảng 20-30 từ)"""
        sentences = [s.strip() for s in text.split('\n') if len(s.strip()) > 20]
        if not sentences:
            return "Kinh nghiệm làm việc"
        return sentences[min(len(sentences)-1, max(0, len(sentences)//2))]

    def evaluate_retrieval(self, sample_size=50):
        """Mode 1: Zero-LLM Evaluation (Chỉ test độ chính xác của ChromaDB)"""
        print(f"🔄 [Mode 1] Đang đọc {sample_size} mẫu từ CSV...")
        if not self.data_path.exists():
            print(f"❌ Không tìm thấy file {self.data_path}")
            return

        df = pd.read_csv(self.data_path)
        sampled_df = df.sample(min(sample_size, len(df)))
        
        retriever = self._get_retriever()
        
        hit_count = 0
        total_latency = 0
        successful_queries = []

        for _, row in sampled_df.iterrows():
            expected_id = str(row['ID'])
            category = row['Category'].upper() if pd.notna(row['Category']) else "HR"
            query = self._generate_query_from_text(str(row['Resume_str']))
            
            tracker = LatencyTracker()
            tracker.start()
            
            # Truy cập trực tiếp ChromaDB để test thuần túy Vector Retrieval
            dept = "hr" if "HR" in category else "information-technology"
            coll_name = f"{dept}_collection"
            try:
                collection = retriever.store.get_collection(coll_name)
                # Bỏ qua LLM, chỉ query VectorDB lấy top 5 chunks
                res = collection.query(query_texts=[query], n_results=5)
                
                tracker.stop()
                total_latency += tracker.latency
                
                # Trích xuất danh sách các source_file từ metadata
                metadatas = res.get("metadatas", [[]])[0]
                sources = [m.get("source_file", "") for m in metadatas]
                
                is_hit = calculate_hit_rate(expected_id, sources)
                if is_hit:
                    hit_count += 1
                    successful_queries.append({
                        "id": expected_id,
                        "query": query,
                        "department": dept
                    })
            except Exception as e:
                # Bỏ qua nếu collection không tồn tại (chưa index)
                pass

        hit_rate = (hit_count / sample_size) * 100 if sample_size else 0
        avg_latency = total_latency / sample_size if sample_size else 0
        
        print("\n" + "="*50)
        print("🎯 KẾT QUẢ MODE 1: RETRIEVAL EVALUATION")
        print("="*50)
        print(f"- Số mẫu test: {sample_size}")
        print(f"- Hit Rate (Chính xác): {hit_rate:.2f}% ({hit_count}/{sample_size})")
        print(f"- Độ trễ truy xuất TB: {avg_latency:.4f} giây")
        
        # Lưu các query thành công để dùng cho Mode 2
        hits_file = self.logs_dir / "mode1_hits.json"
        with open(hits_file, "w", encoding="utf-8") as f:
            json.dump(successful_queries, f, ensure_ascii=False, indent=2)
        print(f"- Đã lưu các câu hỏi Hit vào {hits_file}")

    def evaluate_generation(self, sample_size=15):
        """Mode 2: Micro-Sampling Local LLM (Test tốc độ và khả năng sinh text)"""
        hit_file = self.logs_dir / "mode1_hits.json"
        if not hit_file.exists():
            print("❌ Lỗi: Không tìm thấy mode1_hits.json. Hãy chạy Mode 1 trước!")
            return
            
        with open(hit_file, "r", encoding="utf-8") as f:
            successful_queries = json.load(f)
            
        sampled_queries = successful_queries[:sample_size]
        if not sampled_queries:
            print("❌ Lỗi: Không có câu hỏi hợp lệ nào từ Mode 1!")
            return
            
        print(f"🔄 [Mode 2] Đang test end-to-end với Local LLM ({len(sampled_queries)} mẫu)...")
        results = []
        retriever = self._get_retriever()
        
        for idx, item in enumerate(sampled_queries):
            print(f"⏳ Đang xử lý mẫu {idx+1}/{len(sampled_queries)} (ID: {item['id']})...")
            tracker = LatencyTracker()
            tracker.start()
            
            try:
                # Chạy luồng Full RAG: Vector Retrieval -> Context Injection -> LLM Generation
                answer_dict = retriever.retrieve(query=item["query"], department=item["department"])
                tracker.stop()
                latency = tracker.latency
                
                results.append({
                    "id": item["id"],
                    "query": item["query"],
                    "answer": answer_dict.get("answer", ""),
                    "sources": answer_dict.get("source_coordinates", []),
                    "latency_sec": latency
                })
            except Exception as e:
                print(f"❌ Lỗi xử lý mẫu {item['id']}: {e}")
            
        gen_file = self.logs_dir / "eval_generation.json"
        with open(gen_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        avg_lat = sum(r["latency_sec"] for r in results) / len(results) if results else 0
        
        print("\n" + "="*50)
        print("📝 KẾT QUẢ MODE 2: GENERATION EVALUATION")
        print("="*50)
        print(f"- Đã xử lý thành công: {len(results)} mẫu")
        print(f"- Độ trễ End-to-End TB: {avg_lat:.2f} giây")
        print(f"- File kết quả: {gen_file}")

    async def _fetch_score_from_api(self, session, item, api_key, model_name):
        """Hàm bất đồng bộ (async) để gọi Cloud API chấm điểm"""
        prompt = (
            f"Bạn là một giám khảo nhân sự. Hãy chấm điểm câu trả lời sau dựa trên câu hỏi gốc.\n"
            f"Câu hỏi: {item['query']}\n"
            f"Câu trả lời: {item['answer']}\n"
            f"Hãy cho điểm từ 1 đến 5 về 'Answer Relevance' (Mức độ trả lời đúng trọng tâm). "
            f"Chỉ trả về ĐÚNG MỘT CON SỐ (ví dụ: 5), không giải thích thêm."
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {"contents": [{"parts":[{"text": prompt}]}]}
        
        try:
            async with session.post(url, json=payload, headers={'Content-Type': 'application/json'}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text_resp = data['candidates'][0]['content']['parts'][0]['text']
                    match = re.search(r'\d+', text_resp)
                    score = int(match.group()) if match else 0
                    item["relevance_score"] = min(max(score, 1), 5) # Giới hạn 1-5
                else:
                    item["relevance_score"] = 0 # Lỗi API
        except Exception:
            item["relevance_score"] = 0
            
        return item

    async def evaluate_cloud_judge(self):
        """Mode 3: LLM-as-a-Judge offloading (Dùng async asyncio)"""
        gen_file = self.logs_dir / "eval_generation.json"
        if not gen_file.exists():
            print("❌ Lỗi: Không tìm thấy eval_generation.json. Hãy chạy Mode 2 trước!")
            return
            
        with open(gen_file, "r", encoding="utf-8") as f:
            results = json.load(f)
            
        # Load biến môi trường từ file .env
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash") # Mặc định nếu không cung cấp
        
        if not api_key:
            print("❌ Lỗi: Không tìm thấy GEMINI_API_KEY trong file .env.")
            print("Vui lòng thêm GEMINI_API_KEY=your_api_key_here vào file .env!")
            return
            
        print(f"⚖️ [Mode 3] Đang gọi Cloud Judge ({model_name}) chấm điểm {len(results)} câu trả lời đồng thời...")
        
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_score_from_api(session, item, api_key, model_name) for item in results]
            scored_results = await asyncio.gather(*tasks)
            
        # Trích xuất và lưu báo cáo
        df = pd.DataFrame(scored_results)
        report_path = self.logs_dir / "evaluation_report.csv"
        df.to_csv(report_path, index=False)
        
        valid_scores = [s["relevance_score"] for s in scored_results if s["relevance_score"] > 0]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        print("\n" + "="*50)
        print("☁️ KẾT QUẢ MODE 3: CLOUD JUDGE EVALUATION")
        print("="*50)
        print(f"- Số mẫu đã chấm: {len(scored_results)}")
        print(f"- Điểm Relevance trung bình: {avg_score:.2f} / 5.0")
        print(f"- Báo cáo chi tiết: {report_path}")
