import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="KarAI - Prototype 3.0 Pro", page_icon="K", layout="wide", initial_sidebar_state="expanded")

# --- 2. THEME & CSS KUSTOM ---
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Courier New', Courier, monospace; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 1px solid #333333; }
    [data-testid="stSidebar"] div.stImage { display: flex; justify-content: left; margin-top: -40px; margin-bottom: -20px; }
    [data-testid="stSidebar"] div.stImage img { border-radius: 50%; border: 1px solid #FFFFFF; width: 35px !important; height: 35px !important; object-fit: cover; }
    h1.main-title { color: #FFFFFF !important; text-transform: uppercase; letter-spacing: 2px; font-weight: bold; font-size: 1.8rem !important; }
    .stChatMessage.user { background-color: #1a1a1a; border-radius: 15px 15px 0px 15px; color: white; margin-bottom: 15px; }
    .stChatMessage.assistant { background-color: transparent; border: 1px solid #333333; border-radius: 15px 15px 15px 0px; color: white; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())
if "db_loaded" not in st.session_state: st.session_state.db_loaded = False

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")

# --- 4. FIREBASE LOGIC ---
def save_chat_to_firebase(email, messages):
    if not firebase_url or not email: return
    safe_email = email.replace(".", "_").replace("@", "_")
    url = f"{firebase_url}/chats/{safe_email}.json"
    clean_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    try: requests.put(url, json=clean_messages)
    except: pass

# --- 5. LOGIN GATEWAY (BYPASS) ---
if not st.session_state.user_email:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Futuristic Intelligence - Authorized Access Only</p>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        email = st.text_input("Masukan ID User / Email:")
        if st.button("Masuk Terminal"):
            st.session_state.user_email = email
            # Load Data
            url = f"{firebase_url}/chats/{email.replace('.', '_')}.json"
            res = requests.get(url)
            if res.status_code == 200 and res.json(): st.session_state.messages = res.json()
            st.rerun()
    st.stop()

# --- 6. SIDEBAR & MODEL ---
model_configs = {
    "⚡ Karai Basic": "gemini-2.5-flash-lite",
    "🧠 Karai Expert": "gemini-2.5-pro",
    "🎨 Karai Creative": "gemini-3.5-flash"
}

with st.sidebar:
    try: st.image(Image.open("logo_no_bg.png")) 
    except: pass
    st.write(f"👤 **User:** {st.session_state.user_email}")
    if st.button("🚪 Logout"): 
        st.session_state.user_email = ""; st.session_state.messages = []; st.rerun()
    st.divider()
    mode_karai = st.selectbox("Pilih Model:", list(model_configs.keys()))
    uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
    if st.button("🧹 Clear Chat"):
        st.session_state.messages = []
        save_chat_to_firebase(st.session_state.user_email, [])
        st.rerun()

# --- 7. MAIN CHAT ---
st.markdown("<h1 class='main-title'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel(model_name=model_configs[mode_karai])

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]): st.markdown(message["content"])

if prompt := st.chat_input("Kirim perintah..."):
    img = Image.open(uploaded_file) if uploaded_file else None
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    with st.chat_message("assistant"):
        payload = [prompt, img] if img else [prompt]
        response = model.generate_content(payload)
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        save_chat_to_firebase(st.session_state.user_email, st.session_state.messages)
        st.session_state.uploader_key = str(uuid.uuid4())
        st.rerun()