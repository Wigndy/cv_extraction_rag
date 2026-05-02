import time
from typing import List

def calculate_hit_rate(expected_id: str, retrieved_sources: List[str]) -> bool:
    """
    Tính toán Exact Match Hit Rate.
    Kiểm tra xem ID dự kiến (expected_id) có xuất hiện trong danh sách 
    các source_file được truy xuất từ ChromaDB hay không.
    Ví dụ: expected_id = '10694288' -> Tìm kiếm '10694288.pdf' trong retrieved_sources.
    """
    expected_file = f"{expected_id}.pdf"
    return expected_file in retrieved_sources

class LatencyTracker:
    """
    Công cụ đo lường độ trễ (Latency) cho các pipeline RAG.
    """
    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Bắt đầu đo thời gian."""
        self.start_time = time.time()

    def stop(self):
        """Kết thúc đo thời gian."""
        self.end_time = time.time()

    @property
    def latency(self) -> float:
        """Trả về thời gian trôi qua tính bằng giây."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
