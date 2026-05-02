# AI CV Analysis & RAG Pipeline

Dự án này là một hệ thống phân tích và truy vấn hồ sơ ứng viên (CV) tự động bằng cách ứng dụng kiến trúc RAG (Retrieval-Augmented Generation). Hệ thống cho phép người dùng tìm kiếm thông tin ứng viên trong kho dữ liệu (HR/IT) hoặc tải lên một CV hoàn toàn mới để AI phân tích và trả lời câu hỏi trực tiếp.

## 🏗 Kiến trúc hệ thống (Workflow Pipeline)

Hệ thống được thiết kế thành các giai đoạn (Phases) xử lý tuần tự:

### 1. Dữ liệu đầu vào (Raw Data)
- Kho dữ liệu CV thô ban đầu bao gồm các file PDF ứng viên.
- Danh sách thông tin cơ bản được liệt kê và đối chiếu thông qua file `Resume.csv`.

> **[Nội dung cụ thể quá trình xây dựng - Raw Data]** 
> *(Bạn điền chi tiết về cách bạn thu thập và xử lý data raw ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF mô tả Data Raw]**

### 2. Phase 1: Ingestion (Trích xuất văn bản)
- Đọc và trích xuất nội dung từ các file PDF.
- Áp dụng cơ chế kép: Trích xuất **Text-based** (kéo chữ trực tiếp từ file digital) và kết hợp **OCR (Tesseract)** làm phương án dự phòng (fallback) để xử lý các CV được scan dạng hình ảnh.

> **[Nội dung cụ thể quá trình xây dựng - Phase 1]** 
> *(Bạn điền chi tiết cách bạn build module Ingestion ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF mô tả Phase 1]**

### 3. Phase 2: LLM Extraction (Cấu trúc hóa dữ liệu)
- Toàn bộ văn bản hỗn độn từ Phase 1 được đưa qua mô hình LLM **`qwen2.5:7b`** (chạy cục bộ thông qua Ollama).
- LLM sẽ phân tích và chuẩn hóa lại nội dung tuân thủ nghiêm ngặt theo bộ format JSON được định nghĩa trong `src/extraction/schema.py` (bao gồm Profile, Experience, Education, Projects).

> **[Nội dung cụ thể quá trình xây dựng - Phase 2]** 
> *(Bạn điền chi tiết về Prompting, Schema và xử lý JSON ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF mô tả Phase 2]**

### 4. Phase 3: Semantic Chunking & Indexing
- Dữ liệu JSON sau khi được chuẩn hóa sẽ được **Semantic Chunking** (chia nhỏ theo cụm ngữ nghĩa) để đảm bảo không bị mất ngữ cảnh (Profile, Experience, Edu, Project).
- Sử dụng mô hình **`nomic-embed-text`** để chuyển đổi các đoạn text này thành Vector (Embeddings).
- Lưu trữ toàn bộ Vector vào hệ thống cơ sở dữ liệu **ChromaDB**. (Tạo các Dynamic Collection theo `session_id` để phân lập dữ liệu).

> **[Nội dung cụ thể quá trình xây dựng - Phase 3]** 
> *(Bạn điền chi tiết về Logic Chunking và cách VectorDB tổ chức Collection ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF mô tả Phase 3]**

---

## 🧪 Đánh giá mô hình (Tiered Evaluation)

Hệ thống được thiết kế với Chiến lược Đánh giá Phân tầng (Tiered Evaluation) nhằm tối ưu cho phần cứng giới hạn (MacBook 16GB). Quá trình đánh giá được chia làm 3 Mode thông qua script `run_evaluation.py`:
- **Mode 1 (Retrieval):** Đánh giá độ chính xác (Exact Match Hit Rate) và độ trễ của ChromaDB mà không cần gọi LLM.
- **Mode 2 (Generation):** Micro-sampling qua Local LLM (Qwen2.5:7b) để đo End-to-End Latency.
- **Mode 3 (Cloud Judge):** Tối ưu bất đồng bộ (`asyncio` + `aiohttp`), offload việc chấm điểm sang Cloud API (Google Gemini 2.5 Flash) để đánh giá Answer Relevance (1-5 sao).

> **[Nội dung cụ thể quá trình xây dựng - Evaluation]** 
> *(Bạn điền chi tiết về các metrics đạt được, quá trình chạy 3 Mode và kết quả đánh giá ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF mô tả Evaluation]**

---

## 🚀 Hướng dẫn Triển khai (Deployment & API)

Dự án sử dụng mô hình **Hybrid Deployment** tách biệt Backend và Frontend, giúp tăng tính ổn định:
- **Backend (FastAPI & ChromaDB):** Được đóng gói Docker, chạy Local trên máy tính. Cung cấp các REST API cho tác vụ upload, truy vấn. Đặc biệt xử lý rác dữ liệu bằng hàm cleanup_orphan_collections trong `lifespan` FastAPI.
- **Frontend (Streamlit):** Web UI quản lý session người dùng, được host trực tiếp trên Streamlit Community Cloud (https://windycv.streamlit.app).
- **Kết nối (Ngrok):** Sử dụng Ngrok để tạo đường hầm (tunnel) an toàn từ Streamlit Cloud về Backend Local.

### Các lệnh vận hành:

**1. Khởi động Backend AI Server (Docker)**
Mở Terminal tại thư mục gốc và chạy lệnh:
```bash
# Xây dựng và chạy backend ngầm
docker compose up -d --build

# Tắt backend khi không sử dụng
docker compose down
```

**2. Mở kết nối Tunnel (Ngrok)**
Để Frontend trên Cloud có thể gọi về Backend Local, mở một Terminal mới và chạy:
```bash
ngrok http 8000
```
*Lưu ý: Sau khi chạy, copy URL HTTPS do Ngrok cung cấp và cập nhật vào biến `BACKEND_URL` trong file `frontend/app.py` và Push lên Github để Cloud tự cập nhật.*

**3. Khởi động Frontend Web UI (Chạy Local nếu muốn test trước)**
```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

### Các bất lợi còn tồn tại (Limitations & Trade-offs):
- **Phụ thuộc Ngrok URL:** Link ngrok thay đổi mỗi khi khởi động lại, đòi hỏi phải update thủ công vào code Streamlit mỗi ngày nếu không dùng bản trả phí.
- **Giới hạn phần cứng Local:** Quá trình Ingestion và Inference dùng `qwen2.5:7b` chạy tốn nhiều RAM. Việc đáp ứng truy vấn trực tiếp từ Cloud xuống máy cá nhân có thể gây thắt cổ chai hoặc treo máy nếu có nhiều session tải file cùng lúc.
- **Tính trạng mồ côi (Orphan Sessions):** Do Streamlit làm mới `session_state` mỗi khi người dùng tải lại trang web bằng F5, hệ thống sẽ mất dấu `session_id` cũ. Nếu user không chủ động bấm nút "Xóa CV", các collection tạm thời sẽ lưu lại ổ cứng. (Giải pháp hiện tại là Backend tự động quét rác rải rác mỗi khi Server khởi động lại).

> **[Nội dung cụ thể quá trình xây dựng - Deployment]** 
> *(Bạn điền chi tiết về cách khắc phục lỗi Pydantic, config Docker, cài đặt thư viện cho Streamlit Cloud ở đây)*
> 
> **[Vị trí đặt Hình ảnh/Video/GIF demo UI và Deploy]**
