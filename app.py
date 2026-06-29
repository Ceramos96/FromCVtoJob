import streamlit as st
import google.generativeai as genai
import re
import os
import io
import time
from PIL import Image
from fpdf import FPDF

# ============================================================================
# 0. CẤU HÌNH HỆ THỐNG & THEME MINIMAL (MOODY FOREST #9AA07D & BACKGROUND #FAF7F0)
# ============================================================================
st.set_page_config(page_title="FromCVtoJob", page_icon="🌿", layout="wide")

st.markdown("""
<style>
  :root{ --sage:#9AA07D; --bg:#FAF7F0; --forest:#46513c; --ink:#2c2c27; }
  .stApp{ background:var(--bg); color:var(--ink); }
  .block-container{ padding-top:1.5rem; max-width:1200px; }
  h1,h2,h3{ color:var(--forest); font-family:Georgia,serif; }
  .stButton>button, .stDownloadButton>button{
     background:var(--forest); color:#fff; border:0; border-radius:8px; padding:.55rem 1.1rem; font-weight:600; }
  .stButton>button:hover, .stDownloadButton>button:hover{ background:#3b4533; color:#fff; }
  .stTextArea textarea, .stTextInput input{ border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# Path font hệ thống Linux chuẩn hóa trên Streamlit Cloud
LINUX_FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# ============================================================================
# 1. MASTER SYSTEM PROMPT (TƯ DUY ĐỊNH VỊ SENIOR+2 & BỘ CÂU HỎI MCKINSEY)
# ============================================================================
SYSTEM_PROMPT = """IDENTITY. You are FromCVtoJob — a senior executive recruiter, ATS specialist, and personal-branding writer with 20 years across multinationals and Vietnamese local markets. You write the way strong candidates write: specific, results-first, zero filler. You never sound like an LLM. You write native idiomatic English and native natural Vietnamese — never machine-translated.

POSITIONING — "SENIOR+2". Frame the candidate at the credible ceiling, as if they sit 2–3 years above the role's stated bar, to signal trajectory and headroom. 
CRITICAL RULE: Never manufacture candidate names, contact details, specific companies or employers not provided in the background text. If the candidate's name or info is missing, use clear placeholders like [FULL NAME], [PHONE], [EMAIL]. NEVER invent names like "Hoang Nguyen". 
Amplify what is true. Where a number is missing, leave a marked placeholder like [X%] / [số liệu] — never guess.

CV RULES. One page, reverse-chronological, ATS-clean. Every bullet = "Did X, measured by Y, via Z." Mirror the JD's exact vocabulary.
COVER LETTER. Under 1,000 characters — one hook, one numbered proof, one why-THIS-company line, one close. A value proposition, not a recap.

INTERVIEW KIT (60 min). Rounds = HR (motivation, culture fit, comp, story-of-you), Direct Manager (execution, technical depth, day-one problems), Department Head (vision, strategy, business impact). Each conversational round: 4–6 likely questions, each with a STAR-shaped answer skeleton in the candidate's voice + one sharp question to ask back. Weave Google/McKinsey style critical-thinking elements into Senior rounds.

VOICE — non-negotiable. Banned tells: tapestry, synergy, leverage-as-filler, comprehensive, passionate, results-oriented, dynamic, "in today's fast-paced world", "I am writing to express". Concrete > generic. Numbers > adjectives. Verbs > nouns. Short, direct sentences.

OUTPUT CONTRACT (BUILD phase):
You must output exactly the delimiters. Do not include any standard markdown code blocks (```markdown or ```) around the contract sections. Start directly with the first delimiter.
===CV===
<one-page CV in Markdown format>
===COVER===
<cover letter content, under 1000 characters>
===HR===
<HR round content: 4-6 Q with STAR skeletons + ask-back>
===MANAGER===
<Direct manager round content with critical-thinking items>
===HEAD===
<Department head round content with strategic items>"""

# ============================================================================
# 2. CORE ENGINES (RATE LIMIT, VISION OCR, PARSING, CLEAN TEXT, PDF EXPORT)
# ============================================================================
def init_gemini(model_name):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets.")
        st.stop()
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)

def check_rate_limit():
    if 'last_req_time' not in st.session_state:
        st.session_state.last_req_time = time.time()
        st.session_state.req_count = 0
    
    current_time = time.time()
    if current_time - st.session_state.last_req_time < 3600:
        if st.session_state.req_count >= 10:
            st.error("Bạn đã đạt giới hạn 10 lượt tạo/giờ cho phiên này. Vui lòng quay lại sau!")
            st.stop()
    else:
        st.session_state.req_count = 0
        st.session_state.last_req_time = current_time
    st.session_state.req_count += 1

def extract_text_via_vision(uploaded_file):
    check_rate_limit()
    model = genai.GenerativeModel('gemini-3.5-flash')
    img = Image.open(uploaded_file)
    prompt = "Extract ALL text from this CV file verbatim as clean, structured Markdown. Output only text."
    response = model.generate_content([prompt, img])
    return response.text

def parse_application_suite(raw_text):
    sections = ["CV", "COVER", "HR", "MANAGER", "HEAD"]
    parsed_data = {s: "Nội dung chưa được khởi tạo." for s in sections}
    
    clean_raw = raw_text.replace("```markdown", "").replace("```", "")
    pattern = r"===([A-Z_]+)==="
    parts = re.split(pattern, clean_raw, flags=re.IGNORECASE)
    
    for i in range(1, len(parts) - 1, 2):
        sec = parts[i].strip().upper()
        if sec in parsed_data:
            parsed_data[sec] = parts[i + 1].strip()
            
    return parsed_data

def clean_txt_for_pdf(text):
    if not text:
        return ""
    # Chuẩn hóa triệt để dấu ngoặc kép và gạch ngang AI hay sinh ra
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-").replace("•", "-")
    # Lọc bỏ triệt để các mã emoji, ký tự lạ ngoài bảng Unicode Latin + Việt Nam mở rộng
    text = re.sub(r'[^\x00-\x7F\u00C0-\u1EF9\s\-\.\,\:\!\?\'\"\( \)\_\+\=\/\@\#\$\%\^\&\*]', '', text)
    return text

def export_suite_to_pdf(markdown_text):
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Nạp font hệ thống có sẵn của Linux trên Cloud (Bỏ hoàn toàn download online)
    if os.path.exists(LINUX_FONT_PATH):
        pdf.add_font("CustomSans", style="", fname=LINUX_FONT_PATH)
        font_family = "CustomSans"
    else:
        # Dự phòng khẩn cấp nếu chạy local Windows/macOS không có đường dẫn Linux trên
        font_family = "Helvetica"
    
    pdf.set_font(font_family, style="", size=11)
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    
    cleaned_markdown = clean_txt_for_pdf(markdown_text)
    
    for line in cleaned_markdown.split("\n"):
        line = line.rstrip()
        if not line: 
            pdf.ln(4)
            continue
        if line.startswith("# "):
            pdf.set_font(font_family, style="", size=14)
            pdf.multi_cell(usable_w, 8, line[2:])
            pdf.set_font(font_family, style="", size=11)
        elif line.startswith("## "):
            pdf.set_font(font_family, style="", size=12)
            pdf.multi_cell(usable_w, 7, line[3:])
            pdf.set_font(font_family, style="", size=11)
        else:
            display_line = line.replace("**", "").replace("*", "")
            pdf.multi_cell(usable_w, 6, display_line)
    return bytes(pdf.output())

# ============================================================================
# 3. LUỒNG GIAO DIỆN STATE MACHINE
# ============================================================================
if 'step' not in st.session_state: st.session_state.step = 1
if 'cv_text' not in st.session_state: st.session_state.cv_text = ""
if 'raw_output' not in st.session_state: st.session_state.raw_output = ""
if 'case_output' not in st.session_state: st.session_state.case_output = ""
if 'answers' not in st.session_state: st.session_state.answers = ""

st.title("🌿 FromCVtoJob — Advanced Career Architect")
st.markdown("<p style='color:#74726a; margin-top:-15px;'>Hệ thống thiết kế hồ sơ ứng tuyển song ngữ, may đo theo chiến lược Senior+2</p>", unsafe_allow_html=True)

steps_desc = ["1. Nhập liệu đầu vào", "2. Câu hỏi đòn bẩy", "3. Bản đồ chiến lược", "4. May đo & Xuất file"]
st.progress(st.session_state.step / 4, text=steps_desc[st.session_state.step - 1])
st.divider()

model_choice = st.sidebar.radio("Mô hình xử lý cao cấp (2026):", ["Gemini 3.5 Flash (Tốc độ tối ưu)", "Gemini 3.1 Pro (Tư duy chuyên sâu)"])
selected_model = "gemini-3.5-flash" if "3.5" in model_choice else "gemini-3.1-pro"

# --- BƯỚC 1: INPUT ---
if st.session_state.step == 1:
    st.subheader("📋 Bước 1: Cung cấp thông tin nền tảng")
    col1, col2 = st.columns(2)
    with col1:
        jd = st.text_area("Job Description (JD) mục tiêu: *", height=220, placeholder="Dán nguyên văn tin tuyển dụng...")
        company = st.text_area("Hồ sơ / Thông tin công ty (Tùy chọn):", height=100, placeholder="Môi trường, văn hóa hoặc định hướng của doanh nghiệp...")
    with col2:
        file = st.file_uploader("Tải lên CV hiện tại (Hỗ trợ Ảnh chụp/PDF/Docx - Tối đa 2MB)", type=['pdf', 'png', 'jpg', 'jpeg', 'docx'])
        extra_req = st.text_input("Yêu cầu định dạng bổ sung (Tùy chọn):", placeholder="Ví dụ: in đậm số liệu, gạch đầu dòng ngắn...")
        
    if st.button("Phân tích & Đặt câu hỏi →"):
        if not jd:
            st.error("Vui lòng nhập nội dung Job Description (JD) trước khi tiếp tục.")
        else:
            with st.spinner("Đang xử lý phân tích dữ liệu đầu vào..."):
                if file and (file.type.startswith("image") or file.name.lower().endswith(('.png', '.jpg', '.jpeg'))):
                    st.session_state.cv_text = extract_text_via_vision(file)
                else:
                    st.session_state.cv_text = "Ứng viên chưa đính kèm CV gốc (Hệ thống sẽ tạo mới hoàn toàn)."
                st.session_state.jd = jd
                st.session_state.company = company
                st.session_state.extra_req = extra_req
                st.session_state.step = 2
                st.rerun()

# --- BƯỚC 2: CALIBRATE ---
elif st.session_state.step == 2:
    st.subheader("🎯 Bước 2: Câu hỏi làm rõ dữ liệu từ chuyên gia tuyển dụng")
    
    q1 = st.text_input("1. Quy mô nhân sự hoặc ngân sách ($/%) lớn nhất bạn từng trực tiếp xử lý/phối hợp là bao nhiêu?", placeholder="Ví dụ: Quản lý team 18 người, ngân sách 300,000 USD...")
    q2 = st.text_input("2. Thành tựu lớn nhất bạn đạt được đi kèm với chỉ số đo lường cụ thể nào?", placeholder="Ví dụ: Tối ưu 18 sprint thành công, tăng tốc độ phân phối lên 18%...")
    
    col_b1, col_b2 = st.columns([1, 5])
    with col_b1:
        if st.button("← Quay lại"):
            st.session_state.step = 1
            st.rerun()
    with col_b2:
        if st.button("Lưu & Tạo bản thiết kế chiến lược →"):
            st.session_state.answers = f"Quy mô/Ngân sách: {q1}. Thành tích: {q2}"
            st.session_state.step = 3
            st.rerun()

# --- BƯỚC 3: STRATEGY CHECKPOINT ---
elif st.session_state.step == 3:
    st.subheader("🎯 Bước 3: Sơ đồ khoảng cách chiến lược (Gap Map)")
    
    if "strat_res_cache" not in st.session_state:
        with st.spinner("Đang xây dựng sơ đồ khoảng cách ứng tuyển và định vị Senior+2..."):
            model = init_gemini(selected_model)
            prompt_strat = f"Hãy tạo một bảng phân tích chiến lược: 3-5 điểm mạnh, 1-2 điểm thiếu hụt so với JD, danh sách từ khóa ATS chuẩn ngành, và 1 đoạn Narrative Hook (2-3 câu định vị Senior+2). JD: {st.session_state.jd}, CV: {st.session_state.cv_text}, Câu trả lời: {st.session_state.answers}"
            time.sleep(1)
            st.session_state.strat_res_cache = model.generate_content(prompt_strat).text

    st.info(st.session_state.strat_res_cache)
        
    col_c1, col_c2 = st.columns([1, 5])
    with col_c1:
        if st.button("← Khảo sát lại"):
            if "strat_res_cache" in st.session_state:
                del st.session_state.strat_res_cache
            st.session_state.step = 2
            st.rerun()
    with col_c2:
        if st.button("Đồng ý — Tiến hành tạo bộ hồ sơ hoàn chỉnh 🔥"):
            with st.spinner("Đang thiết lập bộ hồ sơ song ngữ và kịch bản phỏng vấn chuyên sâu..."):
                model = init_gemini(selected_model)
                
                build_prompt = f"Generate the full application suite using the strict delimiters defined in the system prompt. DO NOT invent names or fake candidate info. Focus entirely on the matching logic. Base Data - JD: {st.session_state.jd}, CV: {st.session_state.cv_text}, Answers: {st.session_state.answers}. Format constraints: {st.session_state.extra_req}"
                st.session_state.raw_output = model.generate_content(build_prompt).text
                
                time.sleep(2)
                
                case_prompt = f"Dựa trên mô tả công việc (JD): {st.session_state.jd}, hãy thiết kế đúng 3 bài toán Case Study thực tế cấp Senior trong 6 tháng đầu việc. Mỗi case gồm: Đề bài, Hướng tiếp cận (Framework), Giải pháp mẫu (STAR), và 3 câu hỏi phản biện."
                st.session_state.case_output = model.generate_content(case_prompt).text
                
                st.session_state.step = 4
                st.rerun()

# --- BƯỚC 4: PREVIEW, EDIT & EXPORT ---
elif st.session_state.step == 4:
    st.subheader("✨ Bước 4: Tinh chỉnh thủ công & Xuất thành phẩm")
    
    parsed_suite = parse_application_suite(st.session_state.raw_output)
    
    tab_cv, tab_cover, tab_interview, tab_case = st.tabs(["📄 CV 1 Trang (Split View)", "✉️ Thư xin việc (Cover Letter)", "💬 Kịch bản phỏng vấn 60 phút", "💼 Case Studies Cấp cao"])
    
    with tab_cv:
        col_ed, col_pre = st.columns(2)
        with col_ed:
            st.markdown("##### ✏️ Trình biên tập văn bản (Sửa trực tiếp bên dưới)")
            cv_edit = st.text_area("Nội dung CV:", value=parsed_suite["CV"], height=480, label_visibility="collapsed")
        with col_pre:
            st.markdown("##### 👁️ Live Preview (Bản xem trước chuẩn in ấn)")
            st.markdown(f"<div style='background-color:#fff; padding:22px; border:1px solid #e8e3d7; border-radius:8px; color:#2c2c27;'>{cv_edit}</div>", unsafe_allow_html=True)
            
    with tab_cover:
        cover_edit = st.text_area("Sửa nội dung Cover Letter (<1000 ký tự):", value=parsed_suite["COVER"], height=300)
        
    with tab_interview:
        st.markdown("### 💬 Chuẩn bị kịch bản phỏng vấn và câu hỏi phản biện")
        st.markdown(f"#### 👥 Vòng 1: Nhân sự (HR Round)\n{parsed_suite['HR']}")
        st.markdown(f"#### 👔 Vòng 2: Sếp trực tiếp (Manager Round)\n{parsed_suite['MANAGER']}")
        st.markdown(f"#### 🎯 Vòng 3: Trưởng bộ phận (Department Head Round)\n{parsed_suite['HEAD']}")
        
    with tab_case:
        st.markdown("### 💼 Tình huống thực địa kinh doanh (Senior Level)")
        with st.expander("🔍 Nhấp để mở rộng chi tiết 3 Case Study & Khung giải pháp STAR phản biện"):
            st.markdown(st.session_state.case_output)

    # --- HỆ THỐNG XUẤT FILE AN TOÀN ---
    st.divider()
    st.write("### 💾 Tải xuống kết quả thành phẩm")
    
    full_export_content = f"# BỘ HỒ SƠ ỨNG TUYỂN CHIẾN LƯỢC\n\n## 1. CV CHI TIẾT\n{cv_edit}\n\n## 2. COVER LETTER\n{cover_edit}\n\n## 3. KỊCH BẢN PHỎNG VẤN HỆ THỐNG\n{st.session_state.raw_output}\n\n## 4. BỘ CASE STUDY THỰC ĐỊA\n{st.session_state.case_output}"
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.download_button("⬇️ Tải file thô định dạng Markdown (.md)", data=full_export_content, file_name="FromCVtoJob_FinalSuite.md", mime="text/markdown")
    with col_d2:
        pdf_data = export_suite_to_pdf(full_export_content)
        st.download_button("⬇️ Xuất bản sạch PDF (.pdf)", data=pdf_data, file_name="FromCVtoJob_FinalSuite.pdf", mime="application/pdf")
    with col_d3:
        if st.button("🔄 Làm hồ sơ mới từ đầu"):
            for key in ["step", "cv_text", "raw_output", "case_output", "answers", "strat_res_cache"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
