import streamlit as st
import requests
import uuid
import urllib.parse
import re
import base64
import io

# Library opsional — pastikan ada di requirements.txt
try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from docx import Document as DocxDoc
    from docx.shared import Pt, RGBColor
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

# ============================================================
# 1. SETUP & CSS (MODERN & CLEAN THEME)
# ============================================================
st.set_page_config(page_title="KarAI OS", page_icon="✨", layout="centered")

st.markdown("""
<style>
    /* Sembunyikan branding default Streamlit */
    #MainMenu, header, footer {visibility: hidden;}
    
    /* Area Chat yang Bersih */
    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.8rem 0 !important;
    }
    
    /* Sembunyikan Avatar */
    [data-testid="stChatMessageAvatar"] { display: none; }
    
    /* Bubble User (Rata Kanan, Abu-abu Transparan) */
    [data-testid="stChatMessageUser"] {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessageUser"] > div {
        background-color: rgba(128, 128, 128, 0.15);
        border-radius: 20px;
        padding: 12px 18px !important;
        max-width: 85%;
        margin-left: auto;
    }
    [data-testid="stChatMessageUser"] > div > div {
        text-align: right;
    }
    
    /* Bubble Assistant (Rata Kiri, Tanpa Background) */
    [data-testid="stChatMessageAssistant"] > div {
        background-color: transparent;
        padding: 12px 0 !important;
    }
    
    /* Styling File Uploader agar Minimalis */
    .stFileUploader {
        border: none !important;
        background: transparent !important;
    }
    .stFileUploader > div {
        border: 1px dashed rgba(128,128,128,0.3) !important;
        border-radius: 12px !important;
        padding: 10px !important;
        background-color: rgba(128,128,128,0.05) !important;
    }
    
    /* Sidebar Border Halus */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128,128,128,0.1);
    }
    
    /* Expander untuk Proses Berpikir */
    [data-testid="stExpander"] {
        border: 1px solid rgba(128,128,128,0.2) !important;
        border-radius: 12px !important;
        background-color: rgba(128,128,128,0.05) !important;
    }
    [data-testid="stExpander"] summary {
        font-size: 0.85rem;
        color: rgba(128,128,128,0.8);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. LOAD API KEYS
# ============================================================
firebase_url  = st.secrets.get("FIREBASE_DB_URL", "")
groq_key      = st.secrets.get("GROQ_API_KEY", "")
cerebras_key  = st.secrets.get("CEREBRAS_API_KEY", "")
sambanova_key = st.secrets.get("SAMBANOVA_API_KEY", "")

# ============================================================
# 3. KONFIGURASI MULTI-PROVIDER FALLBACK
# ============================================================
PROVIDERS = [
    {
        "name": "Cerebras", "url": "https://api.cerebras.ai/v1/chat/completions", "key": cerebras_key,
        "models": {"basic": "llama3.1-8b", "expert": "gpt-oss-120b", "listen": "gpt-oss-120b", "smart": "gpt-oss-120b", "default": "llama3.1-8b"}
    },
    {
        "name": "SambaNova", "url": "https://api.sambanova.ai/v1/chat/completions", "key": sambanova_key,
        "models": {"basic": "Meta-Llama-3.1-8B-Instruct", "expert": "Meta-Llama-3.1-70B-Instruct", "listen": "Meta-Llama-3.1-70B-Instruct", "smart": "Meta-Llama-3.1-70B-Instruct", "default": "Meta-Llama-3.1-8B-Instruct"}
    },
    {
        "name": "Groq", "url": "https://api.groq.com/openai/v1/chat/completions", "key": groq_key,
        "models": {"basic": "llama-3.1-8b-instant", "expert": "llama-3.3-70b-versatile", "listen": "llama-3.3-70b-versatile", "smart": "llama-3.3-70b-versatile", "default": "llama-3.1-8b-instant"}
    },
]

IMAGE_TYPES = {"png", "jpg", "jpeg"}
DOC_TYPES   = {"pdf", "docx", "txt", "py", "js", "ts", "jsx", "md", "json", "csv", "html", "css"}
ALL_TYPES   = sorted(IMAGE_TYPES | DOC_TYPES)

WORD_KW = ["file word", "dokumen word", "bikin docx", "buat docx", "buat word", "generate word", "buat laporan", "buat dokumen", "word document", "download word", "simpan word", "format word", "dalam word"]
CODE_KW = ["file python", "script python", "file .py", "download python", "simpan python", "file kode", "python file", "save python", "buat script", "simpan script", "download code", "file js", "simpan js"]

# ============================================================
# 4. FUNGSI DATABASE (FIREBASE)
# ============================================================
def get_user_data(email):
    if not firebase_url: return None
    res = requests.get(f"{firebase_url}/users/{email.replace('.', '_')}.json")
    return res.json() if res.status_code == 200 else None

def save_user(email, password, name, is_premium=False):
    if not firebase_url: return
    requests.put(f"{firebase_url}/users/{email.replace('.', '_')}.json", json={"pw": password, "name": name, "premium": is_premium})

def save_chat(email, msgs, cid):
    if not firebase_url or not email: return
    clean = [{"role": m["role"], "content": m["content"], "dl_key": m.get("dl_key")} for m in msgs]
    requests.put(f"{firebase_url}/chats/{email.replace('.', '_')}/{cid}.json", json=clean)

def get_chat_history(email):
    if not firebase_url or not email: return []
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# ============================================================
# 5. FUNGSI BACA FILE
# ============================================================
def get_file_ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

def extract_file_content(uploaded_file, max_chars=10000):
    name = uploaded_file.name
    ext  = get_file_ext(name)
    try:
        if ext == "pdf":
            if not PDF_OK: return "[ERROR: pdfplumber belum terinstall]"
            pages = []
            with pdfplumber.open(io.BytesIO(uploaded_file.getvalue())) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t: pages.append(t)
            text = "\n\n".join(pages)
        elif ext == "docx":
            if not DOCX_OK: return "[ERROR: python-docx belum terinstall]"
            doc  = DocxDoc(io.BytesIO(uploaded_file.getvalue()))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext in DOC_TYPES:
            text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        else:
            return f"[Format file '.{ext}' belum didukung]"

        if not text.strip(): return f"[File '{name}' tidak mengandung teks]"
        if len(text) > max_chars: text = text[:max_chars] + f"\n\n[... dipotong. File asli {len(text)} karakter]"
        return f"=== Isi file: '{name}' ===\n{text}\n=== Akhir file ==="
    except Exception as e:
        return f"[Gagal membaca file '{name}': {e}]"

# ============================================================
# 6. FUNGSI GENERATE FILE
# ============================================================
def create_word_doc(content, title="Output KarAI"):
    if not DOCX_OK: return None
    doc   = DocxDoc()
    doc.add_heading(title, level=0)
    lines = content.split("\n")
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.name = "Courier New"
                run.font.size = Pt(10)
            continue
        if line.startswith("### "): doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "): doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "): doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith(("- ", "* ")): doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\. ", line): doc.add_paragraph(re.sub(r"^\d+\. ", "", line).strip(), style="List Number")
        elif line.strip() == "": doc.add_paragraph()
        else:
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            clean = re.sub(r"\*(.*?)\*", r"\1", clean)
            clean = re.sub(r"`(.*?)`", r"\1", clean)
            doc.add_paragraph(clean)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def extract_code_block(text):
    match = re.search(r"```(?:\w+)?\n?(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None

def has_code_block(text): return bool(re.search(r"```", text))
def wants_word(prompt): return any(k in prompt.lower() for k in WORD_KW)
def wants_code_file(prompt): return any(k in prompt.lower() for k in CODE_KW)

# ============================================================
# 7. FUNGSI AI
# ============================================================
def detect_mode(selected_model_str):
    if "KBasic" in selected_model_str: return "basic"
    if "KExpert" in selected_model_str: return "expert"
    if "KListen" in selected_model_str: return "listen"
    if "KSmart" in selected_model_str: return "smart"
    return "default"

def call_ai_fallback(messages_payload, selected_model_str):
    mode_key = detect_mode(selected_model_str)
    tried    = []
    for p in PROVIDERS:
        if not p["key"]: continue
        model_name = p["models"].get(mode_key, p["models"]["default"])
        tried.append(p["name"])
        try:
            headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
            res = requests.post(p["url"], headers=headers, json={"model": model_name, "messages": messages_payload}, timeout=30)
            if res.status_code == 200:
                st.caption(f"✅ Dijawab oleh: **{p['name']}** ({model_name})")
                return res.json()["choices"][0]["message"]["content"]
            elif res.status_code == 429:
                st.toast(f"⚠️ {p['name']} penuh, pindah ke cadangan...", icon="🔄")
                continue
        except requests.exceptions.Timeout:
            st.toast(f"⏱️ {p['name']} timeout, coba lain...", icon="🔄")
            continue
        except Exception: continue
    return f"❌ Semua server AI sibuk (dicoba: {', '.join(tried)}). Coba lagi nanti."

def render_ai_message(text):
    match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        think_text = match.group(1).strip()
        main_text  = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        if think_text:
            with st.expander("💭 Proses Berpikir..."): st.markdown(f"*{think_text}*")
            st.markdown(main_text)
    else:
        st.markdown(text)

# ============================================================
# 9. UI: LOGIN & REGISTER
# ============================================================
if "user" not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>KarAI</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔒 Login / Daftar", "🔑 Lupa Password"])
    with tab1:
        email = st.text_input("Email", placeholder="contoh@gmail.com")
        pw    = st.text_input("Password", type="password")
        if st.button("Masuk / Daftar", use_container_width=True):
            if "@" not in email: st.error("Format email salah."); st.stop()
            if len(pw) < 4: st.error("Password minimal 4 karakter."); st.stop()
            data = get_user_data(email)
            if data:
                if data.get("pw") == pw:
                    st.session_state.user = {"email": email, "name": data.get("name", email.split("@")[0]), "premium": data.get("premium", False)}
                    st.rerun()
                else: st.error("Password salah!")
            else:
                name_default = email.split("@")[0]
                save_user(email, pw, name_default, False)
                st.session_state.user = {"email": email, "name": name_default, "premium": False}
                st.rerun()
    with tab2:
        email_reset = st.text_input("Email untuk Reset")
        new_pw      = st.text_input("Password Baru", type="password")
        if st.button("Reset Password", use_container_width=True):
            data = get_user_data(email_reset)
            if data:
                save_user(email_reset, new_pw, data.get("name", email_reset.split("@")[0]), data.get("premium", False))
                st.success("Password berhasil diperbarui!")
            else: st.error("Email belum terdaftar.")
    st.stop()

# ============================================================
# 10. INISIALISASI SESSION STATE
# ============================================================
if "page" not in st.session_state: st.session_state.page = "chat"
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())
if "downloads" not in st.session_state: st.session_state.downloads = {}

# ============================================================
# 11. SIDEBAR (CLEAN & MODERN)
# ============================================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.user['name']}")
    st.divider()
    
    if st.button("➕ Chat Baru", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_id  = str(uuid.uuid4())
        st.rerun()

    models = ["🚀 KBasic", "🧠 KExpert", "👂 KListen"]
    if st.session_state.user.get("premium", False):
        models.extend(["🎨 KCreative", "🔮 KSmart"])
    st.session_state.selected_model = st.selectbox("Mesin AI", models, label_visibility="collapsed")
    
    st.divider()
    st.caption("Riwayat Chat")
    history = get_chat_history(st.session_state.user["email"])
    for cid in history:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(f"Chat: {cid[:6]}...", key=f"btn_{cid}", use_container_width=True):
                url = f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json"
                res = requests.get(url)
                st.session_state.messages = res.json() if res.status_code == 200 and res.json() else []
                st.session_state.chat_id = cid
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{cid}"):
                requests.delete(f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json")
                if st.session_state.chat_id == cid: st.session_state.messages = []
                st.rerun()
    
    st.divider()
    col_set, col_out = st.columns(2)
    with col_set:
        if st.button("⚙️", use_container_width=True): st.session_state.page = "settings"; st.rerun()
    with col_out:
        if st.button("🚪", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# ============================================================
# 12. HALAMAN: PENGATURAN AKUN
# ============================================================
if st.session_state.page == "settings":
    st.title("⚙️ Pengaturan")
    st.write(f"Email: `{st.session_state.user['email']}`")
    new_name = st.text_input("Nama Panggilan", value=st.session_state.user["name"])
    st.divider()
    secret_token = st.text_input("Token Premium", type="password")
    if st.button("💾 Simpan"):
        curr_data  = get_user_data(st.session_state.user["email"])
        pw_to_save = curr_data["pw"] if curr_data else "1234"
        is_premium = curr_data.get("premium", False) if curr_data else False
        if secret_token == "kontolodonmegalodonshark":
            is_premium = True
            st.success("🎉 Token Valid! Fitur Premium dibuka.")
        elif secret_token != "": st.error("❌ Token salah.")
        save_user(st.session_state.user["email"], pw_to_save, new_name, is_premium)
        st.session_state.user["name"] = new_name
        st.session_state.user["premium"] = is_premium
        st.rerun()

# ============================================================
# 13. HALAMAN: CHAT UTAMA
# ============================================================
elif st.session_state.page == "chat":
    st.title("KarAI")
    selected_model = st.session_state.get("selected_model", "🚀 KBasic")
    
    # Render History
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                render_ai_message(m["content"])
                dl_key = m.get("dl_key")
                if dl_key and dl_key in st.session_state.downloads:
                    dl = st.session_state.downloads[dl_key]
                    st.download_button(label=dl["label"], data=dl["data"], file_name=dl["filename"], mime=dl["mime"], key=f"dlbtn_{dl_key}")
            else:
                st.markdown(m["content"])

    # AREA INPUT BAWAH (FILE UPLOADER + CHAT INPUT)
    # File uploader hanya muncul jika mode KSmart
    if "KSmart" in selected_model:
        uploaded_file = st.file_uploader("📎 Lampirkan file (Gambar, PDF, DOCX, Kode)", type=ALL_TYPES, key=st.session_state.uploader_key)
    else:
        uploaded_file = None

    if prompt := st.chat_input("Tanya apa saja pada KarAI..."):
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                ext = get_file_ext(uploaded_file.name)
                if ext in IMAGE_TYPES: st.image(uploaded_file, width=200)
                else: st.caption(f"📎 {uploaded_file.name}")
        
        display_content = prompt
        if uploaded_file and get_file_ext(uploaded_file.name) not in IMAGE_TYPES:
            display_content = f"📎 *[File: {uploaded_file.name}]*\n\n{prompt}"
        st.session_state.messages.append({"role": "user", "content": display_content})

        with st.spinner("⏳ KarAI sedang berpikir..."):
            try:
                ai_response = ""
                dl_key = None

                # MESIN 1: KCREATIVE
                if "KCreative" in selected_model:
                    encoded = urllib.parse.quote(prompt)
                    img_id  = uuid.uuid4().int & 100000
                    img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={img_id}&nologo=true"
                    ai_response = f"Berikut gambar untuk: **{prompt}**\n\n![Generated Image]({img_url})"

                # MESIN 2: KSMART + GAMBAR (Groq Vision)
                elif "KSmart" in selected_model and uploaded_file and get_file_ext(uploaded_file.name) in IMAGE_TYPES:
                    if not groq_key: st.error("⚠️ GROQ_API_KEY belum diisi!"); st.stop()
                    b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                    img_b64 = f"data:image/jpeg;base64,{b64}"
                    msg_vision = []
                    for i, m in enumerate(st.session_state.messages):
                        if i == len(st.session_state.messages) - 1:
                            msg_vision.append({"role": "user", "content": [{"type": "text", "text": m["content"]}, {"type": "image_url", "image_url": {"url": img_b64}}]})
                        else: msg_vision.append({"role": m["role"], "content": m["content"]})
                    
                    # FIX: Menggunakan model vision yang valid di Groq
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}, 
                        json={"model": "llama-3.2-11b-vision-preview", "messages": msg_vision}, timeout=30)
                    ai_response = res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else f"❌ Error Groq Vision: {res.text}"

                # MESIN 3: KSMART + FILE DOKUMEN
                elif "KSmart" in selected_model and uploaded_file and get_file_ext(uploaded_file.name) in DOC_TYPES:
                    file_content = extract_file_content(uploaded_file)
                    msg_doc = []
                    for i, m in enumerate(st.session_state.messages):
                        if i == len(st.session_state.messages) - 1:
                            combined = f"{file_content}\n\n--- Instruksi user ---\n{prompt}"
                            msg_doc.append({"role": "user", "content": combined})
                        else: msg_doc.append({"role": m["role"], "content": m["content"]})
                    ai_response = call_ai_fallback(msg_doc, selected_model)

                # MESIN 4: TEKS BIASA & KLISTEN
                else:
                    messages_payload = []
                    if "KListen" in selected_model:
                        messages_payload.append({
                            "role": "system",
                            "content": (
                                "Kamu adalah KListen, AI teman curhat. Aturan mutlak perilakumu: "
                                "1. Jika pengguna bersedih, galau, atau curhat baik-baik, balaslah dengan "
                                "sangat lembut, menenangkan, dan penuh empati layaknya sahabat. "
                                "2. JIKA pengguna ngegas, berkata kasar, toxic, atau maki-maki duluan, "
                                "KAMU WAJIB MERESPON DENGAN SANGAT GALAK, NGEGAS, DAN MAKI-MAKI BALIK "
                                "TANPA AMPUN. "
                                "Jangan bersikap kaku atau formal, gunakan bahasa gaul Indonesia "
                                "sehari-hari (lu/gw, anjir, astaga, dll)."
                            ),
                        })
                    for m in st.session_state.messages:
                        messages_payload.append({"role": m["role"], "content": m["content"]})
                    ai_response = call_ai_fallback(messages_payload, selected_model)

                # POST-PROCESSING: Generate File
                if wants_word(prompt):
                    if DOCX_OK:
                        word_buf = create_word_doc(ai_response, title=f"KarAI — {prompt[:40]}")
                        if word_buf:
                            dl_key = f"word_{uuid.uuid4().hex[:8]}"
                            st.session_state.downloads[dl_key] = {"label": "📄 Download Word (.docx)", "data": word_buf.getvalue(), "filename": "karai_dokumen.docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                elif wants_code_file(prompt) or has_code_block(ai_response):
                    code = extract_code_block(ai_response)
                    if code:
                        dl_key = f"code_{uuid.uuid4().hex[:8]}"
                        ext_out = "js" if "file js" in prompt.lower() else "py"
                        st.session_state.downloads[dl_key] = {"label": f"🐍 Download kode (.{ext_out})", "data": code.encode("utf-8"), "filename": f"karai_script.{ext_out}", "mime": "text/plain"}

                # Tampilkan & Simpan
                with st.chat_message("assistant"):
                    render_ai_message(ai_response)
                    if dl_key and dl_key in st.session_state.downloads:
                        dl = st.session_state.downloads[dl_key]
                        st.download_button(label=dl["label"], data=dl["data"], file_name=dl["filename"], mime=dl["mime"], key=f"dlbtn_new_{dl_key}")

                st.session_state.messages.append({"role": "assistant", "content": ai_response, "dl_key": dl_key})
                save_chat(st.session_state.user["email"], st.session_state.messages, st.session_state.chat_id)
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()

            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan: {e}")
                if st.session_state.messages: st.session_state.messages.pop()