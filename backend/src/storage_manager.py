import logging
import psutil
import os
from pathlib import Path
from datetime import datetime
import json

def setup_logger(name: str) -> logging.Logger:
    """Setup centralized logging with timestamped files in data/logs/."""
    log_dir = Path(__file__).resolve().parents[1] / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{name}_{timestamp}.log"
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)
        
    return logger

def log_memory_usage(phase_name: str, local_logger: logging.Logger):
    """Memory Guard: Log current memory usage via psutil."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / (1024 * 1024)
    local_logger.info(f"[{phase_name}] Current Memory Usage: {mem_mb:.2f} MB")

def save_json(data: list | dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(path: str | Path) -> list | dict:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
