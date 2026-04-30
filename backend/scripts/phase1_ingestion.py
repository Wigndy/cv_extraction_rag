# python3 scripts/phase1_ingestion.py --dir data/raw/HR --dept HR
# python3 scripts/phase1_ingestion.py --dir data/raw/INFORMATION-TECHNOLOGY --dept INFORMATION-TECHNOLOGY
# import argparse
# import sys
# from pathlib import Path
# import gc

# project_root = Path(__file__).resolve().parents[1]
# sys.path.append(str(project_root))

# from src.ingestion.router import ResumeIngestionRouter
# from src.storage_manager import setup_logger, log_memory_usage, save_json

# logger = setup_logger("phase1_ingestion")

# def main():
#     parser = argparse.ArgumentParser(description="Phase 1: Ingestion (Dual-Stream Extraction)")
#     parser.add_argument("--dir", required=True, help="Directory containing PDF files")
#     parser.add_argument("--dept", required=True, help="Department label (e.g., HR, IT)")
#     args = parser.parse_args()
    
#     input_dir = Path(args.dir)
#     if not input_dir.exists() or not input_dir.is_dir():
#         logger.error(f"Directory {input_dir} does not exist.")
#         sys.exit(1)
        
#     router = ResumeIngestionRouter.from_config()
#     results = []
    
#     pdf_files = list(input_dir.glob("*.pdf"))
#     logger.info(f"Starting Phase 1. Found {len(pdf_files)} PDF files in {input_dir}")
    
#     for i, pdf_path in enumerate(pdf_files):
#         logger.info(f"Processing ({i+1}/{len(pdf_files)}): {pdf_path.name}")
#         log_memory_usage(f"Phase1: After {pdf_path.name}", logger)
        
#     output_path = project_root / "data" / "temp" / f"ingested_{args.dept.lower()}.json"
#     save_json(results, output_path)
#     logger.info(f"Phase 1 complete. Saved {len(results)} records to {output_path}")

# if __name__ == "__main__":
#     main()
import argparse
import sys
import json
from pathlib import Path
import gc

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.ingestion.router import ResumeIngestionRouter
from src.storage_manager import setup_logger, log_memory_usage, save_json

logger = setup_logger("phase1_ingestion")

def load_existing_results(output_path):
    """Đọc dữ liệu đã xử lý từ trước để tránh chạy lại."""
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc file cũ {output_path}: {e}")
    return []

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Ingestion (Dual-Stream Extraction)")
    parser.add_argument("--dir", required=True, help="Directory containing PDF files")
    parser.add_argument("--dept", required=True, help="Department label (e.g., HR, IT)")
    args = parser.parse_args()
    
    input_dir = Path(args.dir)
    output_path = project_root / "data" / "temp" / f"ingested_{args.dept.lower()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Directory {input_dir} does not exist.")
        sys.exit(1)
        
    router = ResumeIngestionRouter.from_config()
    
    # 1. LOAD DỮ LIỆU CŨ (Nếu có)
    results = load_existing_results(output_path)
    processed_files = {res["source_file"] for res in results}
    
    pdf_files = list(input_dir.glob("*.pdf"))
    logger.info(f"Khởi động Phase 1. Tìm thấy {len(pdf_files)} file PDF. Đã xử lý trước đó: {len(processed_files)}")
    
    for i, pdf_path in enumerate(pdf_files):
        # 2. KIỂM TRA TRÙNG LẶP
        if pdf_path.name in processed_files:
            logger.info(f"Bỏ qua (Đã tồn tại): {pdf_path.name}")
            continue

        logger.info(f"Đang xử lý ({i+1}/{len(pdf_files)}): {pdf_path.name}")
        log_memory_usage(f"Phase1: Before {pdf_path.name}", logger)
        
        try:
            payload = router.ingest(pdf_path, department=args.dept)
            new_record = {
                "source_file": pdf_path.name,
                "department": args.dept,
                "digital_text": payload["digital_text"],
                "visual_text": payload["visual_text"],
                "metadata": payload["metadata"]
            }
            results.append(new_record)
            
            # 3. LƯU TỨC THỜI (Lưu sau mỗi file xử lý thành công)
            save_json(results, output_path)
            logger.info(f"Đã lưu tiến độ sau file: {pdf_path.name}")
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất {pdf_path.name}: {e}")
            
        gc.collect()
        log_memory_usage(f"Phase1: After {pdf_path.name}", logger)
        
    logger.info(f"Phase 1 hoàn tất. Tổng cộng {len(results)} bản ghi tại {output_path}")

if __name__ == "__main__":
    main()