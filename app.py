import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIG ---
st.set_page_config(page_title="KarAI Pro", page_icon="K", layout="wide")

st.markdown("""
<style>
    /* Default Dark Mode (Aman) */
    [data-theme="dark"] {
        --bg-color: #000000;
        --text-color: #FFFFFF;
        --sidebar-bg: #0a0a0a;
    }
    /* Light Mode (Tampilannya jadi Bersih/Minimalis) */
    [data-theme="light"] {
        --bg-color: #FFFFFF;
        --text-color: #000000;
        --sidebar-bg: #F0F2F6;
    }
    
    .stApp { 
        background-color: var(--bg-color); 
        color: var(--text-color); 
        font-family: 'Courier New', Courier, monospace; 
    }
    
    [data-testid="stSidebar"] { 
        background-color: var(--sidebar-bg); 
    }
    
    /* Font Color Adaptive */
    h1, h2, h3, p, span, div { color: var(--text-color) !important; }

    /* Chat Styling */
    .stChatMessage { background-color: transparent !important; }
    
    /* Button Google */
    .google-btn { 
        width:100%; padding:12px; background-color:#4285F4; color:white !important; 
        border:none; border-radius:5px; font-weight:bold; text-align:center; 
        text-decoration: none; display: inline-block; 
    }
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
    # ?shallow=true buat ngambil daftar key aja (biar cepet)
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

# --- 4. SIDEBAR & HISTORY ---
with st.sidebar:
    st.write(f"👤 **{st.session_state.user_email}**")
    
    if st.button("➕ Chat Baru"):
        save_chat(st.session_state.user_email, st.session_state.messages, st.session_state.chat_id)
        st.session_state.messages = []
        st.session_state.chat_id = str(uuid.uuid4())
        st.rerun()
        
    st.divider()
    st.subheader("📜 Chat History")
    
    # Ambil list chat
    history = get_chat_history(st.session_state.user_email)
    for cid in history:
        if st.button(f"Chat: {cid[:8]}..."): # Nampilin 8 digit pertama id
            # Load chat lama
            url = f"{firebase_url}/chats/{st.session_state.user_email.replace('.', '_')}/{cid}.json"
            res = requests.get(url)
            if res.status_code == 200:
                st.session_state.messages = res.json()
                st.session_state.chat_id = cid
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