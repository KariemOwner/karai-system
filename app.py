import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import json

# --- 1. CONFIGURATION HARUS PALING ATAS ---
st.set_page_config(page_title="KarAI - Prototype 1", page_icon="K", layout="wide", initial_sidebar_state="expanded")

# --- 2. CONFIG LOGIC & DICTIONARY MODEL ---
model_configs = {
    "⚡ Karai Basic": {
        "api_name": "gemini-2.5-flash-lite",
        "desc": "Jawab sesingkat dan sepadat mungkin, jangan berikan penjelasan panjang. Mirip seperti cuplikan pencarian web."
    },
    "🧠 Karai Expert": {
        "api_name": "gemini-2.5-pro",
        "desc": "Jawab dengan sangat mendalam, teknis, dan step-by-step. Gunakan logika tingkat tinggi."
    },
    "🎨 Karai Creative": {
        "api_name": "gemini-3.5-flash",
        "desc": "Jawab dengan gaya yang kreatif, santai, namun terstruktur. Berikan ide-ide out of the box."
    },
    "🔥 Karai Creative S": {
        "api_name": "gemini-2.0-flash",
        "desc": "Berpikir cepat namun mendalam menggunakan basis arsitektur Flash ter-update. Output luwes layaknya manusia."
    },
    "🌟 Karai Creative X": {
        "api_name": "gemini-2.5-pro",
        "desc": "Model tertinggi dengan penalaran Pro tingkat lanjut yang sangat kompleks, analitis, dan detail maksimal."
    }
}

# --- 3. THEME & CSS KUSTOM (Futuristic B&W - Micro Logo) ---
st.markdown("""
<style>
    /* Main Background & Text Color */
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #222222;
    }
    
    /* Center and Style the MICRO LOGO */
    [data-testid="stSidebar"] div.stImage {
        display: flex;
        justify-content: left;
        margin-top: -40px;
        margin-bottom: -20px;
    }
    [data-testid="stSidebar"] div.stImage img {
        border-radius: 50%;
        border: 1px solid #555555; 
        width: 35px !important;  /* Ukuran logo kecil elegan */
        height: 35px !important;
        object-fit: cover;
    }

    /* Mengubah warna teks judul utama */
    h1.main-title {
        color: #FFFFFF !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: bold;
        font-size: 1.8rem !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }
    p.sub-title {
        color: #666666 !important;
        font-size: 0.8rem !important;
        margin-top: 0px !important;
        padding-top: 0px !important;
        letter-spacing: 1px;
    }

    /* Sidebar headers */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
        font-size: 1rem !important;
    }

    /* Mempercantik Input Elements */
    .stSelectbox div[data-baseweb="select"] > div, .stTextInput input {
        background-color: #111111;
        border: 1px solid #333333;
        color: white;
    }

    /* Mempercantik Info/Success Box */
    .stAlert {
        background-color: #111111;
        color: #FFFFFF;
        border: 1px solid #333333;
    }

    /* CSS Kustom untuk Tampilan Pesan Chat (Chat Bubble) */
    .stChatMessage.user {
        background-color: #111111;
        border-radius: 15px 15px 0px 15px;
        border: 1px solid #222222;
        color: white;
        margin-bottom: 15px;
    }
    .stChatMessage.assistant {
        background-color: transparent;
        border-radius: 15px 15px 15px 0px;
        color: white;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

PREMIUM_LICENSE_KEY = "KARAI-PRO-1337"

# --- 5. LOGIN GATEWAY (SISTEM MOCKUP GRATIS) ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: white; margin-top: 10vh;'>KarAI PROTOTYPE 1</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Futuristic Intelligence by Kariem</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Sistem terkunci. Silakan identifikasi diri lu untuk masuk ke dalam terminal KarAI.")
        login_input = st.text_input("Email Google / Username:")
        if st.button("🌐 Login via Google Auth", use_container_width=True):
            if login_input:
                st.session_state.logged_in = True
                st.session_state.username = login_input
                st.rerun()
            else:
                st.error("Masukkan Email/Username terlebih dahulu!")
    st.stop() # Hentikan proses render aplikasi kalau belum login

# --- 6. API KEY RETRIEVAL LOGIC ---
api_key_env = st.secrets.get("GOOGLE_API_KEY", "")
if not api_key_env:
    api_key_env = st.secrets.get("env", {}).get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
api_key_env = api_key_env.strip().strip('"').strip("'")

# --- 7. SIDEBAR - BRANDING, AUTH & CONFIGURATION ---
with st.sidebar:
    # Micro Logo
    try:
        logo = Image.open("logo_no_bg.png")
        st.image(logo) 
    except FileNotFoundError:
        st.error("Logo 'logo_no_bg.png' gak ketemu!")

    st.write(f"👤 **User:** {st.session_state.username}")
    
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # SECTION 1: LICENSE GATEKEEPING
    st.subheader("🔑 Lisensi Sistem")
    current_key = st.text_input("License Key Premium:", type="password")
    if st.button("Aktivasi"):
        if current_key == PREMIUM_LICENSE_KEY:
            st.session_state.is_premium = True
            st.success("PREMIUM AKTIF!")
        else:
            st.session_state.is_premium = False
            st.error("Kode salah.")

    # SECTION 2: MODEL SELECTION
    st.subheader("🧠 Model AI")
    available_models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if st.session_state.is_premium:
        available_models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])

    mode_karai = st.selectbox("Pilih Model:", available_models)
    current_config = model_configs[mode_karai]
    st.divider()

    # SECTION 3: UPLOAD FOTO & SIMPAN MEMORI
    st.subheader("📎 Attachment & Memori")
    
    # Fitur Upload Gambar
    uploaded_file = st.file_uploader("Upload Foto untuk dianalisis:", type=['png', 'jpg', 'jpeg'])
    
    # Fitur Simpan Chat ke TXT
    if st.session_state.messages:
        chat_history_str = "=== KarAI Chat History ===\n\n"
        for m in st.session_state.messages:
            chat_history_str += f"{m['role'].upper()}: {m['content']}\n\n"
            
        st.download_button(
            label="💾 Download Riwayat Chat",
            data=chat_history_str,
            file_name="KarAI_Memory.txt",
            mime="text/plain",
            use_container_width=True
        )

# --- 8. INITIALIZE AI MODEL ---
if not api_key_env or api_key_env == "":
    st.error("❌ ERROR: API Key kosong.")
    st.stop()

genai.configure(api_key=api_key_env)
model = genai.GenerativeModel(
    model_name=current_config["api_name"],
    system_instruction=current_config["desc"]
)

# --- 9. MAIN CHAT AREA ---
# Judul Utama & Subtitle yang sudah diperbaiki
st.markdown("<h1 class='main-title'>KarAI PROTOTYPE 1</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Futuristic Intelligence by Kariem</p>", unsafe_allow_html=True)

# Tampilkan history chat (beserta gambarnya jika ada)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "image" in message and message["image"] is not None:
            st.image(message["image"], width=200)

# Jalur input chat user
if prompt := st.chat_input("Kirim perintah ke KarAI..."):
    
    # Cek apakah user mau mengirim teks beserta gambar
    img_to_send = None
    if uploaded_file is not None:
        img_to_send = Image.open(uploaded_file)

    # Simpan ke history state
    st.session_state.messages.append({"role": "user", "content": prompt, "image": img_to_send})
    
    # Tampilkan pesan user di layar
    with st.chat_message("user"):
        st.markdown(prompt)
        if img_to_send:
            st.image(img_to_send, width=200)

    # Eksekusi ke Gemini
    with st.chat_message("assistant"):
        with st.spinner(f'{mode_karai} sedang menganalisis...'):
            try:
                # Menyiapkan payload. Jika ada gambar, kirim sebagai list [teks, gambar]
                payload = [prompt]
                if img_to_send:
                    payload.append(img_to_send)

                response = model.generate_content(payload)
                st.markdown(response.text)
                
                # Hitung Token
                try:
                    in_t = model.count_tokens(payload).total_tokens
                    out_t = model.count_tokens(response.text).total_tokens
                    st.session_state.total_tokens += (in_t + out_t)
                except:
                    pass 
                
                # Simpan balasan AI ke history
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()

            except Exception as e:
                st.error(f"Koneksi terputus: {e}")