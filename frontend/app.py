import streamlit as st
import requests
import json
import uuid

# BACKEND_URL = "http://localhost:8000"
BACKEND_URL = "https://heading-quill-lizard.ngrok-free.dev"

def check_backend_health():
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

st.set_page_config(page_title="AI CV Analysis", layout="wide")

if not check_backend_health():
    st.error("🚨 Vui lòng bật Local AI Server (FastAPI Backend) để tiếp tục.")
    st.stop()

st.title("AI CV Analysis & RAG Pipeline")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state or st.session_state.session_id is None:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.has_uploaded = False

with st.sidebar:
    st.header("1. Cấu hình tìm kiếm")
    context_mode = st.radio(
        "Chế độ dữ liệu:",
        ["Department Base Data", "Uploaded Session Data"],
        index=0
    )
    
    department = None
    if context_mode == "Department Base Data":
        department = st.selectbox("Chọn Department Database:", ["HR", "Information-Technology"])
        
    st.markdown("---")
    st.header("2. Upload CV mới (Dynamic Pipeline)")
    uploaded_pdf = st.file_uploader("Tải lên file CV (PDF)", type=["pdf"])
    
    if uploaded_pdf:
        if st.button("🚀 Process & Index CV"):
            with st.spinner("Đang chạy luồng Ingestion -> LLM Extraction -> Chunking -> Temp Collection..."):
                try:
                    files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
                    data = {
                        "department": "temp_session", 
                        "extraction_mode": "Auto",
                        "session_id": st.session_state.session_id
                    }
                    res = requests.post(f"{BACKEND_URL}/api/upload", files=files, data=data)
                    
                    if res.status_code == 200:
                        payload = res.json()
                        st.session_state.session_id = payload.get("session_id")
                        st.session_state.has_uploaded = True
                        st.success(f"Xử lý thành công! Đã tạo {payload.get('indexed_chunks')} chunks.")
                        st.info("Chuyển chế độ dữ liệu sang 'Uploaded Session Data' để chat với CV này.")
                    else:
                        st.error(f"Lỗi từ Backend: {res.text}")
                except Exception as e:
                    st.error(f"Lỗi kết nối: {str(e)}")
                    
    st.markdown("---")
    st.header("3. Dọn dẹp dữ liệu (Cleanup)")
    if st.button("🗑 Xóa CV / Clear Session"):
        with st.spinner("Đang xóa dữ liệu tạm thời..."):
            try:
                res = requests.delete(f"{BACKEND_URL}/api/cleanup/{st.session_state.session_id}")
                if res.status_code == 200:
                    st.success("Đã xóa dữ liệu tạm thời của phiên này.")
                    # Sinh ID mới cho phiên tiếp theo để tránh xung đột
                    st.session_state.session_id = str(uuid.uuid4())
                    st.session_state.has_uploaded = False
                    st.session_state.messages = []
                else:
                    st.error(f"Lỗi từ Backend: {res.text}")
            except Exception as e:
                st.error(f"Lỗi kết nối: {str(e)}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Hỏi về ứng viên...")
if question:
    if context_mode == "Uploaded Session Data" and not st.session_state.get("has_uploaded", False):
        st.warning("Vui lòng tải lên và xử lý một CV trước khi chat ở chế độ Uploaded Session Data.")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Hệ thống đang suy nghĩ..."):
            try:
                payload = {
                    "query": question,
                    "department": department,
                    "session_id": st.session_state.session_id,
                    "context_mode": context_mode
                }
                res = requests.post(f"{BACKEND_URL}/api/query", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "Lỗi: Không có câu trả lời.")
                    sources = data.get("source_coordinates", [])
                    if sources:
                        answer += f"\n\n**Nguồn:** {', '.join(set(sources))}"
                        
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"Lỗi từ Backend: {res.text}")
            except Exception as e:
                st.error(f"Lỗi kết nối: {str(e)}")
