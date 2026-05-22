import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# --- 1. CONFIGURATION HARUS PALING ATAS ---
st.set_page_config(page_title="KarAI - Futuristic Intelligence", page_icon="K", layout="wide", initial_sidebar_state="expanded")

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

# --- 3. THEME & CSS KUSTOM (Futuristic B&W - Small Transparent Logo) ---
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
        border-right: 1px solid #333333;
    }
    
    /* Center and Style the Sidebar Logo */
    [data-testid="stSidebar"] div.stImage {
        display: flex;
        justify-content: center;
        margin-top: -30px; /* Pull up towards top */
        margin-bottom: 0px;
    }
    [data-testid="stSidebar"] div.stImage img {
        border-radius: 50%;
        border: 2px solid #FFFFFF; /* Gahar border */
        width: 80px !important; /* Small width */
        height: 80px !important;
        object-fit: cover;
    }

    /* Mengubah warna teks judul di sidebar */
    [data-testid="stSidebar"] h1 {
        color: #FFFFFF !important;
        text-align: center;
        font-size: 1.5rem !important;
        margin-top: 10px !important;
        letter-spacing: 2px;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p {
        color: #FFFFFF !important;
    }

    /* Mempercantik tampilan Selectbox di sidebar */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #111111;
        border: 1px solid #333333;
        color: white;
    }
    
    /* Mempercantik Input Teks (License Key) */
    .stTextInput input {
        background-color: #111111;
        color: white;
        border: 1px solid #333333;
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

# --- 4. SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

# KODE RAHASIA UNTUK PREMIUM MAPPING
PREMIUM_LICENSE_KEY = "KARAI-PRO-1337"

# --- 5. API KEY RETRIEVAL LOGIC (Bypass regular env cache) ---
# Mencoba membaca dari direct/flat Streamlit Secrets untuk menghindari cache OS
api_key_env = st.secrets.get("GOOGLE_API_KEY", "")

if not api_key_env:
    # Backup check jika format [env] masih dipakai
    api_key_env = st.secrets.get("env", {}).get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

# Bersihkan karakter hantu
api_key_env = api_key_env.strip().strip('"').strip("'")

# --- 6. SIDEBAR - BRANDING, AUTH & CONFIGURATION ---
with st.sidebar:
    # Menampilkan Logo K kepunyaan Kariem (Versi No BG)
    try:
        # Mencoba membuka file logo baru yang sudah dihapus backgroundnya
        logo = Image.open("logo_no_bg.png")
        # Menampilkan tanpa use_column_width agar CSS bisa kontrol size
        st.image(logo) 
    except FileNotFoundError:
        st.error("Error: File 'logo_no_bg.png' gak ketemu. Hapus BG logo lu, save PNG, namain 'logo_no_bg.png', taruh di folder yang sama!")

    st.title("KarAI SYSTEM")
    st.write("Futuristic Intelligence by Kariem.")
    
    # DEBUGGING TOOL: Menampilkan mask key asli yang sedang dibaca server
    if api_key_env:
        masked_key = f"{api_key_env[:7]}...{api_key_env[-5:]}" if len(api_key_env) > 12 else "Terlalu Pendek"
        st.text(f"📡 Server Key: {masked_key}")
    else:
        st.text("📡 Server Key: GAK DETEKSI")
    st.divider()

    # SECTION 1: AUTH & LICENSE GATEKEEPING
    st.subheader("🔑 Autentikasi Sistem")
    
    # Input License Key
    current_key = st.text_input("Masukin License Key Premium:", type="password")
    
    if st.button("Aktivasi Lisensi"):
        if current_key == PREMIUM_LICENSE_KEY:
            st.session_state.is_premium = True
            st.success("STATUS: PREMIUM AKTIF!")
            st.rerun()
        else:
            st.session_state.is_premium = False
            st.error("Lisensi Gagal: Kode salah.")

    # Tampilkan Status User
    status_label = "💎 Premium Active" if st.session_state.is_premium else "👤 Basic User"
    st.info(f"STATUS: **{status_label}**")
    st.divider()

    # SECTION 2: MODEL SELECTION & TIERING
    st.subheader("🧠 Mode Pemikiran AI")

    # Batasi pilihan model berdasarkan status premium
    available_models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if st.session_state.is_premium:
        available_models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])

    mode_karai = st.selectbox("Pilih Tingkatan Model:", available_models)
    
    # Mengambil konfigurasi model yang dipilih (Aman karena model_configs di atas)
    current_config = model_configs[mode_karai]
    
    st.write(f"ℹ️ *Prompt: {current_config['desc']}*")
    st.divider()

    # SECTION 3: TOKEN USE TRACKER
    st.subheader("💾 Monitor Token Sesi")
    st.metric(label="Total Token Terpakai", value=f"{st.session_state.total_tokens:,}")

# --- 7. INITIALIZE AI MODEL ---
if not api_key_env or api_key_env == "":
    st.error("❌ ERROR SISTEM: API Key kosong di server. Tolong isi Secrets Streamlit Cloud lu.")
    st.stop()

genai.configure(api_key=api_key_env)

# Bikin objek model AI sesuai pilihan user yang aktif
model = genai.GenerativeModel(
    model_name=current_config["api_name"],
    system_instruction=current_config["desc"]
)

# --- 8. MAIN CHAT AREA ---
st.title("🤖 KarAI SYSTEM")
st.write(f"Tingkatan: **{mode_karai}**")

# Tampilkan history chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Jalur input chat user
if prompt := st.chat_input("Kirim perintah ke KarAI..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f'Processing {mode_karai}...'):
            try:
                response = model.generate_content(prompt)
                st.markdown(response.text)
                
                # Hitung Token balik menggunakan logika internal API
                try:
                    in_t = model.count_tokens(prompt).total_tokens
                    out_t = model.count_tokens(response.text).total_tokens
                    total_turn = in_t + out_t
                    st.write(f"📊 *Token turn ini: {total_turn:,}*")
                    st.session_state.total_tokens += total_turn
                except:
                    pass # Skip jika kuota counter token sibuk
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()

            except Exception as e:
                st.error(f"Koneksi terputus atau API bermasalah: {e}")