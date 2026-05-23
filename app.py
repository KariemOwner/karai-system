import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid, requests, time
from google.api_core import exceptions

# --- 1. CONFIG & FUTURISTIC CSS (SAFE THEME) ---
st.set_page_config(page_title="KarAI OS", page_icon="🌐", layout="wide")

st.markdown("""
<style>
    /* Font Cyberpunk / Terminal */
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Share Tech Mono', monospace;
    }
    
    /* Efek Chat Bubble: Hilangkan kotak, ganti dengan garis aksen di kiri */
    .stChatMessage { 
        background-color: transparent !important; 
        border-left: 3px solid var(--primary-color) !important; 
        padding-left: 15px !important; 
        margin-bottom: 20px !important;
    }
    .stChatMessage > div { border: none !important; }
    
    /* Biarkan warna teks diurus otomatis oleh Streamlit */
    .stMarkdown { color: inherit !important; }
    
    /* Sidebar dengan gaya garis putus-putus */
    [data-testid="stSidebar"] { 
        border-right: 1px dashed rgba(128, 128, 128, 0.4); 
    }
    
    /* Header Kustom */
    .cyber-header {
        text-align: center;
        letter-spacing: 4px;
        text-transform: uppercase;
        border-bottom: 1px solid var(--primary-color);
        padding-bottom: 10px;
        margin-bottom: 30px;
        font-weight: bold;
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
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# --- 3. LOGIN TERMINAL ---
if not st.session_state.user_email:
    st.markdown("<h1 class='cyber-header'>SYS.LOGIN // KarAI OS</h1>", unsafe_allow_html=True)
    with st.columns([1,2,1])[1]:
        email = st.text_input("ENTER ACCESS ID:")
        if st.button("INITIALIZE CONNECTION"):
            st.session_state.user_email = email
            st.rerun()
    st.stop()

# --- 4. SIDEBAR (CONTROL PANEL) ---
with st.sidebar:
    try: st.image("logo_no_bg.png", width=70)
    except: st.markdown("<h2 style='text-align:center;'>KarAI</h2>", unsafe_allow_html=True)
    
    st.write(f"📡 **USER:** `{st.session_state.user_email}`")
    
    if st.button("➕ NEW THREAD"):
        st.session_state.messages = []
        st.session_state.chat_id = str(uuid.uuid4())
        st.rerun()
        
    st.divider()
    
    models = ["⚡ Karai Basic", "🧠 Karai Expert", "🎨 Karai Creative"]
    if "ikram" in st.session_state.user_email.lower(): models.extend(["🔥 Karai Creative S", "🌟 Karai Creative X"])
    mode = st.selectbox("LLM ENGINE:", models)
    
    uploaded_file = st.file_uploader("UPLOAD VISION DATA:", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
    
    st.divider()
    st.subheader("📁 DATA LOGS")
    history = get_chat_history(st.session_state.user_email)
    for cid in history:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(f"LOG: {cid[:6]}...", key=f"btn_{cid}"):
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
    if st.button("TERMINATE SESSION"): 
        st.session_state.user_email = ""
        st.session_state.messages = []
        st.rerun()

# --- 5. MAIN CHAT INTERFACE ---
st.markdown("<h1 class='cyber-header'>KarAI // SYSTEM ACTIVE</h1>", unsafe_allow_html=True)
genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

# Tampilkan history chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# Input dan proses
if prompt := st.chat_input("TRANSMIT MESSAGE..."):
    img = Image.open(uploaded_file) if uploaded_file else None
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt)
        if img: st.image(img, width=200)
    
    with st.spinner("⏳ PROCESSING DATA..."):
        try:
            payload = [prompt, img] if img else [prompt]
            res = model.generate_content(payload)
            
            st.chat_message("assistant").markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            
            # Auto-save ke database
            save_chat(st.session_state.user_email, st.session_state.messages, st.session_state.chat_id)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()
            
        except exceptions.ResourceExhausted:
            st.error("⚠️ [SYS.ERROR] API Rate Limit Exceeded. Auto-retrying in 10 seconds...")
            time.sleep(10)
            st.rerun()
            
        except Exception as e:
            st.error(f"FATAL ERROR: {e}")