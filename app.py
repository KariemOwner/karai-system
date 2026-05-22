import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# --- 1. CONFIGURATION HARUS PALING ATAS ---
st.set_page_config(page_title="KarAI - Futuristic Intelligence", page_icon="K", layout="wide", initial_sidebar_state="expanded")

# --- 2. THEME & CSS KUSTOM (Simple Black & White Futuristic) ---
st.markdown("""
<style>
    /* Main Background & Text Color */
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
        font-family: 'Courier New', Courier, monospace; /* Futuristic Font */
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #333333;
    }
    
    /* Mengubah warna teks judul di sidebar */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }

    /* Mempercantik tampilan Selectbox di sidebar */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #111111;
        border: 1px solid #333333;
        color: white;
    }
    .stSelectbox div[data-baseweb="select"] > div:hover {
        border-color: #666666;
    }
    
    /* Mempercantik Input Teks (License Key) */
    .stTextInput input {
        background-color: #111111;
        color: white;
        border: 1px solid #333333;
    }
    .stTextInput input:focus {
        border-color: #FFFFFF;
    }

    /* Mempercantik Info/Success Box */
    .stAlert {
        background-color: #111111;
        color: #FFFFFF;
        border: 1px solid #333333;
    }

    /* CSS Kustom untuk Tampilan Pesan Chat (Chat Bubble) */
    .stChatMessage.user {
        background-color: #1a1a1a;
        border-radius: 15px 15px 0px 15px;
        color: white;
        margin-bottom: 15px;
    }
    .stChatMessage.assistant {
        background-color: #000000;
        border: 1px solid #333333;
        border-radius: 15px 15px 15px 0px;
        color: white;
        margin-bottom: 15px;
    }
    
    /* Header/Title Utama */
    h1 {
        color: #FFFFFF !important;
        text-transform: uppercase;
        letter-spacing: 3px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0
if "license_key_validated" not in st.session_state:
    st.session_state.license_key_validated = False

# KODE RAHASIA UNTUK PREMIU. Ganti ini sesuai keinginan.
# Ini cuma gatekeeping sederhana biar cepet jadi.
PREMIUM_LICENSE_KEY = "KARAI-PRO-1337"

# --- 4. SIDEBAR - BRANDING, AUTH & TOKEN ---
with st.sidebar:
    # Menampilkan Logo
    try:
        logo = Image.open("logo.png")
        st.image(logo, use_column_width=True)
    except FileNotFoundError:
        st.error("Error: File 'logo.png' gak ketemu. Simpan gambar K putih di latar hitam di folder yang sama dengan app.py!")

    st.title("KarAI SYSTEM v1.0")
    st.write("Futuristic Intelligence by Kariem.")
    st.divider()

    # SECTION 1: AUTH & LICENSE GATEKEEPING
    st.subheader("🔑 Autentikasi Sistem")
    
    # Input License Key
    current_key = st.text_input("Masukin License Key Premium:", type="password", help="Dapatkan lisensi dari Kariem Official.")
    
    if st.button("Aktivasi Lisensi"):
        if current_key == PREMIUM_LICENSE_KEY:
            st.session_state.is_premium = True
            st.session_state.license_key_validated = True
            st.success("STATUS: PREMIUM AKTIF. Selamat menikmati Creative S & X!")
        else:
            st.session_state.is_premium = False
            st.session_state.license_key_validated = False
            st.error("Lisensi Gagal: Kode lisensi salah.")

    # Tampilkan Status
    status_label = "💎 Premium" if st.session_state.is_premium else "👤 Basic User"
    st.info(f"STATUS AKUN MU: **{status_label}**")
    st.divider()

    # SECTION 2: MODEL SELECTION & TIERING
    st.subheader("🧠 Mode Pemikiran AI")
    
    # Daftar model dasar untuk Free
    model_options = [
        ("⚡ Karai Basic", "Jawab sesingkat dan sepadat mungkin, seperti cuplikan pencarian web."),
        ("🧠 Karai Expert", "Jawab dengan sangat mendalam, teknis, dan step-by-step. Gunakan logika tingkat tinggi."),
        ("🎨 Karai Creative", "Jawab dengan gaya yang kreatif, santai, namun terstruktur. Berikan ide-ide out of the box.")
    ]
    
    # Daftar model premium
    premium_model_options = [
        ("🔥 Karai Creative S", "Jawab dengan logika Flash yang sangat mendalam dan teknis. Ini adalah mode Flash Pro."),
        ("🌟 Karai Creative X", "Jawab dengan logika Pro yang super mendalam, multimodal, dan kompleks. Ini adalah mode Pro Ultimate.")
    ]

    # Gabungkan model jika Premium
    available_models = [m[0] for m in model_options]
    if st.session_state.is_premium:
        available_models.extend([m[0] for m in premium_model_options])

    # Pilih model
    mode_karai = st.selectbox("Pilih Tingkatan Model:", available_models)
    
    # Tampilkan Deskripsi Model yang dipilih
    current_description = ""
    for name, desc in (model_options + premium_model_options):
        if name == mode_karai:
            current_description = desc
            break
    
    st.write(f"ℹ️ **Instruksi Aktif:** *{current_description}*")
    st.divider()

    # SECTION 3: TOKEN USE TRACKER
    st.subheader("💾 Monitor Token")
    st.metric(label="Total Token Sesi Ini", value=f"{st.session_state.total_tokens:,}", help="Jumlah total token (input + output) yang digunakan selama web ini belum di-refresh.")

# --- 5. INITIALIZE AI MODEL ---
# Ambil API Key dari Secrets (baca panduan di follow-up!)
api_key_env = os.environ.get("GOOGLE_API_KEY")

if not api_key_env:
    st.error("API KEY GAK KETEMU. Lu harus setting 'GOOGLE_API_KEY' di Secrets Management Streamlit Cloud sebelum nge-deploy!")
    st.stop()

genai.configure(api_key=api_key_env)

# Petakan model_karai ke nama model API asli
model_map = {
    "⚡ Karai Basic": "gemini-2.5-flash-lite",
    "🧠 Karai Expert": "gemini-2.5-pro",
    "🎨 Karai Creative": "gemini-3.5-flash",
    "🔥 Karai Creative S": "gemini-2.0-flash", # Flash Mendalam
    "🌟 Karai Creative X": "gemini-2.5-pro"    # Pro Mendalam
}

nama_model_api = model_map.get(mode_karai, "gemini-2.5-flash-lite")

# Inisialisasi Model AI dengan instruksi sistem
model = genai.GenerativeModel(
    model_name=nama_model_api,
    system_instruction=current_description
)

# --- 6. MAIN CHAT AREA ---
st.title("🤖 KarAI SYSTEM")
st.write(f"Sedang beroperasi pada mode **{mode_karai}**.")

# Tampilkan history chat (jika ada)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input Chat
if prompt := st.chat_input("Ketik pertanyaan lu untuk KarAI di sini..."):
    
    # Simpan dan tampilkan pesan dari user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Tampilkan loading saat KarAI mikir, lalu munculin jawabannya
    with st.chat_message("assistant"):
        with st.spinner(f'{mode_karai} sedang memproses data...'):
            try:
                # Ngirim pesan ke AI
                response = model.generate_content(prompt)
                
                # Nampilin jawaban AI
                st.markdown(response.text)
                
                # --- HITUNG TOKEN ---
                # Menggunakan library asli untuk menghitung token secara akurat
                input_tokens = model.count_tokens(prompt).total_tokens
                output_tokens = model.count_tokens(response.text).total_tokens
                total_turn_tokens = input_tokens + output_tokens
                
                # Tampilkan info token untuk turn ini
                st.write(f"📝 *Token used this turn: {total_turn_tokens:,} (Input: {input_tokens:,}, Output: {output_tokens:,})*")
                
                # Update total token sesi
                st.session_state.total_tokens += total_turn_tokens
                
                # Simpan jawaban KarAI ke memori
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
                # Refresh sidebar buat update token total metric
                st.rerun()

            except Exception as e:
                st.error(f"Error saat menghubungi API: {e}")