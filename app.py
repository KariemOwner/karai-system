import streamlit as st
import google.generativeai as genai
from PIL import Image
import os, io, uuid, requests

# --- 1. CONFIG ---
st.set_page_config(page_title="KarAI Pro", page_icon="K", layout="wide")

# --- 2. CSS STABIL (TIDAK LAGI MEMAKSA WARNA) ---
# Kita cuma ngebunuh border/background boxy, biar clean kayak ChatGPT
st.markdown("""
<style>
    /* Hilangin kotak background chat */
    .stChatMessage { background-color: transparent !important; padding: 5px !important; }
    .stChatMessage > div { border: none !important; }
    
    /* Biarin Streamlit yang nentuin warna font */
    .stMarkdown { color: inherit !important; }
    
    /* Sidebar biar tetep elegan tapi gak maksain warna */
    [data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,0.2); }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION & DATABASE ---
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

# --- 4. LOGIN ---
if not st.session_state.user_email:
    st.markdown("<h1 style='text-align:center;'>KarAI PROTOTYPE 3.0</h1>", unsafe_allow_html=True)
    with st.columns([1,2,1])[1]:
        email = st.text_input("Enter ID:")
        if st.button("Masuk"):
            st.session_state.user_email = email
            st.rerun()
    st.stop()

# --- 5. SIDEBAR (STABLE) ---
with st.sidebar:
    try: st.image("logo_no_bg.png", width=60)
    except: st.write("KarAI")
    
    st.write(f"👤 **{st.session_state.user_email}**")
    
    if st.button("➕ Chat Baru"):
        st.session_state.messages = []
        st.session_state.chat_id = str(uuid.uuid4())
        st.rerun()
        
    st.divider()
    
    models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if "ikram" in st.session_state.user_email.lower(): models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode = st.selectbox("Model:", models)
    
    uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
    
    st.divider()
    st.subheader("📜 History")
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

# --- 6. CHAT ENGINE (FIXED) ---
st.title("KarAI")
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Tanya KarAI..."):
    img = Image.open(uploaded_file) if uploaded_file else None
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt)
        if img: st.image(img, width=200)
    
    with st.spinner("KarAI sedang berpikir..."):
        try:
            payload = [prompt, img] if img else [prompt]
            res = model.generate_content(payload)
            st.chat_message("assistant").markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            save_chat(st.session_state.user_email, st.session_state.messages, st.session_state.chat_id)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")