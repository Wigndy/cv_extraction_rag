# python3 scripts/phase2_extraction.py --input data/temp/ingested_hr.json --dept hr
# python3 scripts/phase2_extraction.py --input data/temp/ingested_information-technology.json --dept it

import argparse
import sys
from pathlib import Path
import gc

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.extraction.processor import ResumeExtractor
from src.storage_manager import setup_logger, log_memory_usage, save_json, load_json

logger = setup_logger("phase2_extraction")

def main():
    parser = argparse.ArgumentParser(description="Phase 2: LLM Extraction")
    parser.add_argument("--input", required=True, help="Input JSON file from Phase 1")
    parser.add_argument("--dept", required=False, help="Department label (optional)")
    args = parser.parse_args()
    
    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"Input file {input_file} does not exist.")
        sys.exit(1)
        
    records = load_json(input_file)
    if not records:
        logger.warning(f"No records found in {input_file}")
        return
        
    # Deterministic Ordering: explicitly sort by source_file alphabetically
    records = sorted(records, key=lambda x: x.get("source_file", ""))
    
    logger.info(f"Starting Phase 2. Loaded {len(records)} records.")
    
    dept = args.dept or records[0].get("department", "unknown").lower()
    output_path = project_root / "data" / "processed" / f"{dept}_extracted.json"
    
    # Checkpointing Logic
    existing_records = load_json(output_path) if output_path.exists() else []
    # processed_files = {r.get("metadata", {}).get("source_file") for r in existing_records}
    processed_files = {r.get("source_file") for r in existing_records if r.get("source_file")}    
    extractor = ResumeExtractor()
    
    for i, record in enumerate(records):
        source_file = record.get("source_file", "unknown")
        if source_file in processed_files:
            logger.info(f"Skipping {source_file} (Already processed. Checkpoint active)")
            continue
            
        logger.info(f"Extracting ({i+1}/{len(records)}): {source_file}")
        log_memory_usage(f"Phase2: Before {source_file}", logger)
        
        try:
            digital_text = record.get("digital_text")
            visual_text = record.get("visual_text")
            
            # Sequential Processing (Ollama API call)
            extracted_data = extractor.extract(digital_text=digital_text, visual_text=visual_text)
            
            final_record = {
                "source_file": source_file,
                "digital_text": digital_text,
                "visual_text": visual_text,
                "metadata": record["metadata"],
                "extracted": extracted_data.model_dump(mode='json') if hasattr(extracted_data, 'model_dump') else extracted_data
            }
            existing_records.append(final_record)
            
            # Atomic Saving: Update output file immediately
            save_json(existing_records, output_path)
            logger.info(f"Successfully saved validated JSON for {source_file}")
            processed_files.add(source_file)
        except Exception as e:
            logger.error(f"Error extracting {source_file}: {e}")
            
        # Memory Management: Clear RAM
        gc.collect()
        log_memory_usage(f"Phase2: After {source_file}", logger)
        
    logger.info(f"Phase 2 complete. Total {len(existing_records)} valid records in {output_path}")

if __name__ == "__main__":
    main()
