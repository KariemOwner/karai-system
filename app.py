import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIG & CSS (STABIL & ADAPTIVE) ---
st.set_page_config(page_title="KarAI Pro", page_icon="K", layout="wide")

st.markdown("""
<style>
    /* Styling Dasar */
    body { font-family: 'Courier New', monospace; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 1px solid #333333; }
    .stChatMessage { background-color: transparent !important; padding: 10px !important; }
    
    /* Tombol Delete */
    .delete-btn { background: none; border: none; cursor: pointer; color: #ff4b4b; }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION & DATABASE ---
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")

def save_chat(email, msgs, cid):
    if not firebase_url or not email: return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}/{cid}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

def get_chat_history(email):
    if not firebase_url or not email: return []
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# --- 3. LOGIN ---
if not st.session_state.user_email:
    st.markdown("<h1 style='text-align:center;'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    with st.columns([1,2,1])[1]:
        email = st.text_input("Enter ID:")
        if st.button("Masuk"):
            st.session_state.user_email = email
            st.rerun()
    st.stop()

# --- 4. SIDEBAR (MODEL + HISTORY + DELETE) ---
with st.sidebar:
    try: st.image("logo_no_bg.png", width=60)
    except: st.write("KarAI")
    st.write(f"👤 **{st.session_state.user_email}**")
    
    # Tombol Chat Baru
    if st.button("➕ Chat Baru"):
        st.session_state.messages = []
        st.session_state.chat_id = str(uuid.uuid4())
        st.rerun()
        
    st.divider() # Garis dashboard balik
    
    # Model Selector
    models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if "ikram" in st.session_state.user_email.lower(): models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode = st.selectbox("Model:", models)
    
    st.divider()
    st.subheader("📜 History")
    
    # Daftar History dengan Tombol Hapus
    history = get_chat_history(st.session_state.user_email)
    for cid in history:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(f"Chat: {cid[:6]}...", key=f"btn_{cid}"):
                url = f"{firebase_url}/chats/{st.session_state.user_email.replace('.', '_')}/{cid}.json"
                st.session_state.messages = requests.get(url).json() or []
                st.session_state.chat_id = cid
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{cid}"):
                requests.delete(f"{firebase_url}/chats/{st.session_state.user_email.replace('.', '_')}/{cid}.json")
                if st.session_state.chat_id == cid: st.session_state.messages = []
                st.rerun()

    st.divider()
    if st.button("Logout"): st.session_state.user_email = ""; st.session_state.messages = []; st.rerun()

# --- 5. CHAT ---
st.title("KarAI")
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Tanya KarAI..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    with st.spinner("⏳ KarAI sedang berpikir..."):
        try:
            res = model.generate_content(prompt)
            st.chat_message("assistant").markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            save_chat(st.session_state.user_email, st.session_state.messages, st.session_state.chat_id)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")