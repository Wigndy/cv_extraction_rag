# python3 scripts/run_evaluation.py --mode retrieval
# python3 scripts/run_evaluation.py --mode generation
# python3 scripts/run_evaluation.py --mode cloud-judge

import argparse
import sys
import asyncio
from pathlib import Path

# Thêm đường dẫn project_root vào PYTHONPATH để chạy module src
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.evaluation.evaluator import RAGEvaluator

def main():
    parser = argparse.ArgumentParser(description="Tiered RAG Evaluation Script")
    parser.add_argument(
        "--mode", 
        type=str, 
        required=True, 
        choices=["retrieval", "generation", "cloud-judge"],
        help="Chế độ đánh giá (retrieval: test DB, generation: test Local LLM, cloud-judge: chấm điểm API)"
    )
    
    args = parser.parse_args()
    
    evaluator = RAGEvaluator()
    
    if args.mode == "retrieval":
        # Mode 1: Lấy 50 mẫu ngẫu nhiên để test độ chính xác ChromaDB
        evaluator.evaluate_retrieval(sample_size=50)
        
    elif args.mode == "generation":
        # Mode 2: Lấy 15 câu hỏi (đã Hit) chạy qua Qwen để đo Latency End-to-End
        evaluator.evaluate_generation(sample_size=15)
        
    elif args.mode == "cloud-judge":
        # Mode 3: Gọi Cloud API (Gemini/OpenAI) để chấm điểm câu trả lời
        # Sử dụng asyncio.run vì hàm này dùng aiohttp bất đồng bộ
        asyncio.run(evaluator.evaluate_cloud_judge())

if __name__ == "__main__":
    main()
