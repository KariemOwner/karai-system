import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIG ---
st.set_page_config(page_title="KarAI Pro", page_icon="K", layout="wide")

# --- 2. CLEAN CSS (Anti-Broke) ---
st.markdown("""
<style>
    /* Chat bubbles */
    .stChatMessage { background-color: transparent !important; padding: 10px !important; }
    /* Font */
    body { font-family: 'Courier New', monospace; }
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #0a0a0a; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION & DATABASE ---
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")

def save_chat(email, msgs):
    if not firebase_url or not email: return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

# --- 4. LOGIN ---
if not st.session_state.user_email:
    st.markdown("<h1 style='text-align:center;'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    with st.columns([1,2,1])[1]:
        email = st.text_input("Enter ID:")
        if st.button("Masuk"):
            st.session_state.user_email = email
            res = requests.get(f"{firebase_url}/chats/{email.replace('.', '_')}.json")
            if res.status_code == 200 and res.json(): st.session_state.messages = res.json()
            st.rerun()
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    try: st.image("logo_no_bg.png", width=60)
    except: st.write("KarAI")
    st.write(f"👤 {st.session_state.user_email}")
    
    # Model
    models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if "ikram" in st.session_state.user_email.lower(): models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode = st.selectbox("Model:", models)
    
    uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg'], key=st.session_state.uploader_key)
    if st.button("Logout"): st.session_state.user_email = ""; st.session_state.messages = []; st.rerun()

# --- 6. CHAT ---
st.title("KarAI")
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Tanya KarAI..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    # Native Spinner (Anti-Error)
    with st.spinner("⏳ KarAI sedang berpikir..."):
        try:
            res = model.generate_content(prompt)
            st.chat_message("assistant").markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            save_chat(st.session_state.user_email, st.session_state.messages)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")