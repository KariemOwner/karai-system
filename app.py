import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import io
import uuid
import requests
import urllib.parse

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="KarAI - Prototype 3.0", page_icon="K", layout="wide", initial_sidebar_state="expanded")

# --- 2. THEME & CSS KUSTOM ---
st.markdown("""
<style>
    .stApp { font-family: 'Courier New', Courier, monospace; }
    [data-testid="stSidebar"] div.stImage { display: flex; justify-content: left; margin-top: -40px; margin-bottom: -20px; }
    [data-testid="stSidebar"] div.stImage img { border-radius: 50%; border: 1px solid var(--text-color); width: 35px !important; height: 35px !important; object-fit: cover; }
    h1.main-title { color: var(--text-color) !important; text-transform: uppercase; letter-spacing: 2px; font-weight: bold; font-size: 1.8rem !important; margin-bottom: 0px !important; padding-bottom: 0px !important; }
    p.sub-title { color: gray !important; font-size: 0.8rem !important; margin-top: 0px !important; padding-top: 0px !important; letter-spacing: 1px; }
    .stChatMessage.user { background-color: var(--secondary-background-color); border-radius: 15px 15px 0px 15px; border: 1px solid var(--border-color); margin-bottom: 15px; }
    .stChatMessage.assistant { background-color: transparent; border-radius: 15px 15px 15px 0px; margin-bottom: 15px; }
    .google-btn { width:100%; padding:12px; background-color:#4285F4; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer; text-align:center; font-family: sans-serif; text-decoration: none; display: inline-block; }
    .google-btn:hover { background-color:#3367D6; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "is_premium" not in st.session_state: st.session_state.is_premium = False
if "messages" not in st.session_state: st.session_state.messages = []
if "total_tokens" not in st.session_state: st.session_state.total_tokens = 0
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())
if "db_loaded" not in st.session_state: st.session_state.db_loaded = False

# --- 4. SECRETS & CLOUD KEYS ---
api_key_env = st.secrets.get("GOOGLE_API_KEY", "")
client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
firebase_url = st.secrets.get("FIREBASE_DB_URL", "")
# Pastikan ini sama persis dengan yang ada di Google Cloud (tanpa garis miring di akhir)
redirect_uri = "https://karaiprototype1.streamlit.app" 

PREMIUM_LICENSE_KEY = "KARAI-PRO-1337"

# --- 5. FIREBASE DATABASE LOGIC ---
def save_chat_to_firebase(email, messages):
    if not firebase_url: return
    safe_email = email.replace(".", "_").replace("@", "_")
    url = f"{firebase_url}/chats/{safe_email}.json"
    clean_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    try: requests.put(url, json=clean_messages)
    except: pass

def load_chat_from_firebase(email):
    if not firebase_url: return []
    safe_email = email.replace(".", "_").replace("@", "_")
    url = f"{firebase_url}/chats/{safe_email}.json"
    try:
        res = requests.get(url)
        if res.status_code == 200 and res.json(): return res.json()
    except: pass
    return []

# --- 6. GOOGLE OAUTH LOGIN LOGIC (ANTI BLANK SCREEN) ---
if "code" in st.query_params and not st.session_state.logged_in:
    code = st.query_params["code"]
    
    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        res = requests.post(token_url, data=data)
        token_data = res.json()
        
        # Penangkap Eror: Jika Google menolak token
        if "error" in token_data:
            st.error(f"❌ Gagal Login ke Google: {token_data.get('error_description', token_data.get('error'))}")
            st.info("Sistem membersihkan jalur koneksi. Silakan coba klik tombol login lagi.")
            st.query_params.clear()
            st.stop()
            
        access_token = token_data.get("access_token")
        
        if access_token:
            user_info_url = "https://www.googleapis.com/oauth2/v1/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_res = requests.get(user_info_url, headers=headers).json()
            
            st.session_state.logged_in = True
            st.session_state.user_email = user_res.get("email", "")
            st.session_state.user_name = user_res.get("name", "User")
            
            # Auto Premium untuk Kariem
            if "ikram" in st.session_state.user_email.lower():
                st.session_state.is_premium = True
            else:
                st.session_state.is_premium = False
            
            st.query_params.clear()
            st.rerun()
        else:
            st.error("❌ Eror Fatal: Tidak mendapatkan Access Token dari Google.")
            st.query_params.clear()
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Sistem Crash saat menyambung ke Google: {e}")
        st.query_params.clear()
        st.stop()

# TAMPILAN GERBANG LOGIN
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;' class='main-title'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;' class='sub-title'>Secured Intelligence by Kariem</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if client_id and client_secret:
            st.success("🔒 Sistem Diamankan oleh Google OAuth 2.0")
            encoded_redirect = urllib.parse.quote(redirect_uri, safe='')
            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={encoded_redirect}&response_type=code&scope=openid%20email%20profile"
            st.markdown(f'<a href="{auth_url}" target="_self" class="google-btn">🌐 Sign in with Google</a>', unsafe_allow_html=True)
        else:
            st.error("Google Auth Credentials belum terpasang di Secrets.")
    st.stop()

# --- 7. LOAD HISTORY DARI CLOUD DB ---
if st.session_state.logged_in and not st.session_state.db_loaded:
    cloud_history = load_chat_from_firebase(st.session_state.user_email)
    if cloud_history:
        st.session_state.messages = cloud_history
    st.session_state.db_loaded = True

# --- 8. CONFIG LOGIC & DICTIONARY MODEL ---
model_configs = {
    "⚡ Karai Basic": {"api_name": "gemini-2.5-flash-lite", "desc": "Jawab sesingkat mungkin. Mirip hasil web."},
    "🧠 Karai Expert": {"api_name": "gemini-2.5-pro", "desc": "Jawab sangat mendalam, teknis, step-by-step."},
    "🎨 Karai Creative": {"api_name": "gemini-3.5-flash", "desc": "Jawab kreatif, santai, banyak ide."},
    "🔥 Karai Creative S": {"api_name": "gemini-2.0-flash", "desc": "Analisis mendalam pakai arsitektur Flash."},
    "🌟 Karai Creative X": {"api_name": "gemini-2.5-pro", "desc": "Model tertinggi, Pro tingkat lanjut."}
}

# --- 9. SIDEBAR ---
with st.sidebar:
    try: st.image(Image.open("logo_no_bg.png")) 
    except: pass

    st.write(f"👤 **{st.session_state.user_name}**")
    st.caption(f"{st.session_state.user_email}")
    
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.messages = []
        st.session_state.db_loaded = False
        st.rerun()
    st.divider()

    st.subheader("🧠 Model AI")
    available_models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if st.session_state.is_premium: available_models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode_karai = st.selectbox("Pilih Model:", available_models)
    current_config = model_configs[mode_karai]
    st.divider()

    st.subheader("📎 Attachment")
    uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
    
    st.divider()
    st.subheader("💾 Status Database")
    st.success("🟢 Sync: Cloud Realtime DB")
    
    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        save_chat_to_firebase(st.session_state.user_email, [])
        st.rerun()

# --- 10. INITIALIZE AI MODEL ---
api_key_clean = api_key_env.strip().strip('"').strip("'")
genai.configure(api_key=api_key_clean)
model = genai.GenerativeModel(model_name=current_config["api_name"], system_instruction=current_config["desc"])

# --- 11. MAIN CHAT AREA ---
st.markdown("<h1 class='main-title'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "image" in message and message["image"] is not None:
            st.image(message["image"], width=200)
            
            img_buf = io.BytesIO()
            message["image"].save(img_buf, format="PNG")
            st.download_button(label="⬇️ Download Foto Ini", data=img_buf.getvalue(), file_name=f"KarAI_History_{i}.png", mime="image/png", key=f"dl_btn_{i}")

if prompt := st.chat_input("Kirim perintah ke KarAI..."):
    img_to_send = None
    if uploaded_file is not None: img_to_send = Image.open(uploaded_file)

    st.session_state.messages.append({"role": "user", "content": prompt, "image": img_to_send})
    
    with st.chat_message("user"):
        st.markdown(prompt)
        if img_to_send: st.image(img_to_send, width=200)

    with st.chat_message("assistant"):
        with st.spinner(f'{mode_karai} memproses...'):
            try:
                payload = [prompt]
                if img_to_send: payload.append(img_to_send)
                response = model.generate_content(payload)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                save_chat_to_firebase(st.session_state.user_email, st.session_state.messages)
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")