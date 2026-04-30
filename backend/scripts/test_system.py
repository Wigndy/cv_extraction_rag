import argparse
import sys
import time
import psutil
from pathlib import Path
from typing import Any, Dict

# Add project root to sys.path to import local modules
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.rag.retriever import ResumeRetriever
from src.storage_manager import setup_logger

logger = setup_logger("system_testing")

class RAGTester:
    def __init__(self):
        # Initialize the retriever and current process for monitoring
        self.retriever = ResumeRetriever.from_config()
        self.process = psutil.Process()

    def _get_mem_usage(self) -> float:
        """Returns the current RAM usage in MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def run_test_case(self, name: str, query: str, department: str, expected_type: str = None):
        logger.info(f"--- TEST CASE: {name} ---")
        
        mem_before = self._get_mem_usage()
        start_time = time.time()
        
        # Execute Retrieval and Generation
        result = self.retriever.retrieve(query=query, department=department)
        
        end_time = time.time()
        mem_after = self._get_mem_usage()
        
        duration = end_time - start_time
        mem_diff = mem_after - mem_before
        
        # 1. Display Retrieval Results (Measures Embedding intelligence)
        print(f"\n[QUERY]: {query}")
        # Displaying the top 2 sources found in metadata
        print(f"\n[METADATA SOURCES]: {result.get('metadatas', [])[:2]}...") 
        
        # 2. Display the Grounded Answer
        print(f"\n[ANSWER]:\n{result['answer']}")
        
        # 3. Performance Metrics (MacBook Guard monitoring)
        # Rough estimation: 1 token approx. 4 characters
        tokens_est = len(result['answer']) / 4  
        tps = tokens_est / duration if duration > 0 else 0
        
        print("-" * 30)
        print(f"⏱  Duration: {duration:.2f}s")
        print(f"🚀 Tokens/s (est): {tps:.2f}")
        print(f"🧠 RAM Usage: {mem_after:.2f} MB (Change: {mem_diff:+.2f} MB)")
        print("-" * 30 + "\n")

def main():
    tester = RAGTester()

    # Test Case 1: Pure Retrieval (Specific vs. Ambiguous)
    tester.run_test_case(
        "Specific Retrieval", 
        "Find candidates with experience using PeopleSoft or Oracle HRIS.", 
        "hr"
    )
    
    tester.run_test_case(
        "Ambiguous Retrieval", 
        "I need to find someone capable of managing complex recruitment processes.", 
        "hr"
    )

    # Test Case 2: Cross-Collection Isolation
    # Verifies if IT queries are correctly blocked/handled when pointed at the HR collection
    tester.run_test_case(
        "Isolation Test (IT query in HR collection)", 
        "Who knows Python programming and YOLO architecture?", 
        "hr"
    )

    # Test Case 3: Grounded Answer (Coordinate Accuracy)
    # Checks if the LLM correctly cites the specific source file
    tester.run_test_case(
        "Grounded Answer (File 10399912.pdf)", 
        "Please list the educational background of the candidate in file 10399912.pdf.", 
        "hr"
    )

    tester.run_test_case(
        "HR_EDU_SPECIFIC",
        "What are the educational qualifications listed in file 20417897.pdf?",
        "hr"
    )

    # 2. Experience - Semantic Search (Kiểm tra tìm kiếm theo ý nghĩa công việc)
    tester.run_test_case(
        "HR_EXP_SEMANTIC",
        "Find candidates who have extensive experience in data entry and clerical support.",
        "hr"
    )

    # 3. Personal Info - Skills (Kiểm tra khả năng tổng hợp kỹ năng từ Profile chunk)
    tester.run_test_case(
        "HR_SKILLS_AGGREGATION",
        "Summarize the administrative and software skills for candidate 25724495.pdf.",
        "hr"
    )

    # 4. Experience - Tools (Kiểm tra tìm kiếm công cụ đặc thù như PeopleSoft)
    tester.run_test_case(
        "HR_TOOLS_SEARCH",
        "Identify candidates who have worked with PeopleSoft or HRIS database management.",
        "hr"
    )

    # 5. Education - Institution (Tìm kiếm theo tên trường học)
    tester.run_test_case(
        "HR_EDU_INSTITUTION",
        "List candidates who studied at Montclair State University.",
        "hr"
    )

    # --- DOMAIN: INFORMATION TECHNOLOGY (IT) ---

    # 6. Experience - Technical Stack (Kiểm tra khả năng hiểu thuật ngữ AI/CV)
    tester.run_test_case(
        "IT_EXP_AI",
        "Search for developers with expertise in Computer Vision, specifically YOLO or Mask2Former.",
        "information-technology"
    )

    # 7. Education - Academic Level (Tìm kiếm theo cấp bậc học vấn)
    tester.run_test_case(
        "IT_EDU_LEVEL",
        "List all candidates who hold a Master's degree or higher in Computer Science.",
        "information-technology"
    )

    # 8. Personal Info - Summary (Kiểm tra khả năng tóm tắt định hướng nghề nghiệp)
    tester.run_test_case(
        "IT_SUMMARY_GOAL",
        "Based on the profile summary of candidate 36856210.pdf, summary for me",
        "information-technology"
    )

    # 10. Complex Query - Mixed Info (Kết hợp cả Education và Experience)
    tester.run_test_case(
        "IT_COMPLEX_PROFILE",
        "List candidates who studied at Florence Darlington Technical School.",
        "information-technology"
    )
# "Find candidates with a degree from Bloomsburg University of Pennsylvania." it
# "Identify developers who have experience with YOLO or Computer Vision models."
if __name__ == "__main__":
    main()