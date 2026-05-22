import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIG & CSS (AI-NATIVE STYLE) ---
st.set_page_config(page_title="KarAI Pro", page_icon="K", layout="wide")

st.markdown("""
<style>
    /* Gemini-Style Chat (No Boxes) */
    .stChatMessage { border: none !important; background: transparent !important; margin-bottom: 20px; }
    .stChatMessage > div { border: none !important; }
    
    /* Custom Loading Spinner */
    @keyframes spin { 100% { transform: rotate(360deg); } }
    .loading-container { display: flex; align-items: center; gap: 10px; font-family: monospace; }
    .loading-logo { width: 30px; height: 30px; border-radius: 50%; animation: spin 2s linear infinite; }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE ---
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")

# --- 3. PREMIUM LOGIC ---
def is_premium_user(email):
    # Logika Premium: email lu atau kode khusus
    return "ikram" in email.lower() or "admin" in email.lower()

# --- 4. FIREBASE ---
def save_chat(email, msgs):
    if not firebase_url or not email: return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

# --- 5. LOGIN (BYPASS) ---
if not st.session_state.user_email:
    st.markdown("<h1 style='text-align:center;'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    with st.columns([1,2,1])[1]:
        email = st.text_input("Enter ID:")
        if st.button("Masuk Terminal"):
            st.session_state.user_email = email
            res = requests.get(f"{firebase_url}/chats/{email.replace('.', '_')}.json")
            if res.status_code == 200 and res.json(): st.session_state.messages = res.json()
            st.rerun()
    st.stop()

# --- 6. SIDEBAR & PREMIUM FEATURES ---
with st.sidebar:
    try: st.image("logo_no_bg.png", width=60)
    except: pass
    st.write(f"👤 **{st.session_state.user_email}**")
    st.caption("💎 PREMIUM ACTIVE" if is_premium_user(st.session_state.user_email) else "👤 BASIC USER")
    
    # Model
    models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if is_premium_user(st.session_state.user_email): models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode = st.selectbox("Pilih Model:", models)
    
    uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg'], key=st.session_state.uploader_key)
    if st.button("🚪 Logout"): st.session_state.user_email = ""; st.session_state.messages = []; st.rerun()

# --- 7. CHAT AREA ---
st.markdown("<h1 class='main-title'>KarAI</h1>", unsafe_allow_html=True)
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Tanya KarAI..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    # Animasi Loading
    with st.chat_message("assistant"):
        with st.container():
            st.markdown(f"""
                <div class="loading-container">
                    <img src="https://i.ibb.co/5YgJzG8/logo-no-bg.png" class="loading-logo">
                    <span>⏳ Sedang Berpikir...</span>
                </div>
            """, unsafe_allow_html=True)
            
            res = model.generate_content(prompt)
            st.markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            save_chat(st.session_state.user_email, st.session_state.messages)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()