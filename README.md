# AI CV Analysis & RAG Pipeline

Dự án này là một hệ thống phân tích và truy vấn hồ sơ ứng viên (CV) tự động bằng cách ứng dụng kiến trúc RAG (Retrieval-Augmented Generation). Hệ thống cho phép người dùng tìm kiếm thông tin ứng viên trong kho dữ liệu (HR/IT) hoặc tải lên một CV hoàn toàn mới để AI phân tích và trả lời câu hỏi trực tiếp.

## 🏗 Kiến trúc hệ thống (Workflow Pipeline)

Hệ thống được thiết kế thành các giai đoạn (Phases) xử lý tuần tự, từ dữ liệu thô đến cơ sở dữ liệu Vector và cuối cùng là Web App UI:

### 1. Dữ liệu đầu vào (Raw Data)
- Kho dữ liệu CV thô ban đầu bao gồm các file PDF ứng viên.
- Danh sách thông tin cơ bản được liệt kê và đối chiếu thông qua file `Resume.csv`.

### 2. Phase 1: Ingestion (Trích xuất văn bản)
- Đọc và trích xuất nội dung từ các file PDF.
- Áp dụng cơ chế kép: Trích xuất **Text-based** (kéo chữ trực tiếp từ file digital) và kết hợp **OCR (Tesseract)** làm phương án dự phòng (fallback) để xử lý các CV được scan dạng hình ảnh.

### 3. Phase 2: LLM Extraction (Cấu trúc hóa dữ liệu)
- Toàn bộ văn bản hỗn độn từ Phase 1 được đưa qua mô hình LLM **`qwen2.5:7b`** (chạy cục bộ thông qua Ollama).
- LLM sẽ phân tích và chuẩn hóa lại nội dung tuân thủ nghiêm ngặt theo bộ format JSON được định nghĩa trong `src/extraction/schema.py` (bao gồm Profile, Experience, Education, Projects).

### 4. Phase 3: Semantic Chunking & Indexing
- Dữ liệu JSON sau khi được chuẩn hóa sẽ được **Semantic Chunking** (chia nhỏ theo cụm ngữ nghĩa) để đảm bảo không bị mất ngữ cảnh.
- Sử dụng mô hình **`nomic-embed-text`** để chuyển đổi các đoạn text này thành Vector (Embeddings).
- Lưu trữ toàn bộ Vector vào hệ thống cơ sở dữ liệu **ChromaDB**.

---

## 🚀 Hướng dẫn Triển khai (Deployment)

Dự án sử dụng mô hình **Hybrid Deployment** tách biệt Backend và Frontend, giúp tăng tính ổn định và linh hoạt:

- **Backend (FastAPI & ChromaDB):** Được đóng gói Docker, đảm nhiệm toàn bộ quy trình Ingestion, Extraction, Indexing, và Retrieval.
- **Frontend (Streamlit):** Web UI gọi REST API tới Backend. Hoàn toàn stateless và nhẹ bén, có thể dễ dàng host trên Streamlit Community Cloud.

### Các lệnh vận hành:

**1. Khởi động Backend AI Server (Docker)**
Mở Terminal tại thư mục gốc và chạy lệnh:
```bash
docker-compose up -d --build
```

*(Lệnh khác dành cho Docker)*
- Để tắt Backend:
  ```bash
  docker compose down
  ```
- Để chạy riêng một container (nếu cần debug):
  ```bash
  docker compose run resume-rag-api
  ```

**2. Khởi động Frontend Web UI (Streamlit)**
Mở một Terminal khác, cài đặt thư viện cho frontend và khởi chạy:
```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

---

## 🧪 Đánh giá mô hình (Evaluation)
*Lưu ý: Phần Evaluation Framework (RAGAS / Trulens) hiện đang trong quá trình phát triển để đánh giá độ chính xác của ngữ cảnh truy xuất (Context Precision/Recall). Tài liệu sẽ được cập nhật sau khi module này hoàn thiện.*
