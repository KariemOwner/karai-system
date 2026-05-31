import streamlit as st
import google.generativeai as genai
import requests
import uuid

# --- 1. SETUP & CSS ---
st.set_page_config(page_title="KarAI OS", page_icon="🤖", layout="centered")

st.markdown("""
<style>
    .stChatMessage { padding: 10px; border-radius: 10px; margin-bottom: 15px; }
    [data-testid="stChatMessageUser"] { 
        background-color: rgba(33, 150, 243, 0.1); 
        flex-direction: row-reverse; 
    }
    [data-testid="stChatMessageUser"] > div { text-align: right; }
    [data-testid="stChatMessageAvatar"] { display: none; }
    [data-testid="stSpinner"] > div > div { display: none !important; }
    [data-testid="stSpinner"] { background-color: transparent !important; color: inherit !important; }
</style>
""", unsafe_allow_html=True)

# AMBIL SEMUA API KEY DARI SECRETS
firebase_url = st.secrets.get("FIREBASE_DB_URL", "")
groq_key = st.secrets.get("GROQ_API_KEY", "")
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
openai_key = st.secrets.get("OPENAI_API_KEY", "")

# --- 2. DATABASE LOGIC (FIREBASE) ---
def get_user_data(email):
    if not firebase_url: return None
    res = requests.get(f"{firebase_url}/users/{email.replace('.', '_')}.json")
    return res.json() if res.status_code == 200 else None

def save_user(email, password, name):
    if not firebase_url: return
    requests.put(f"{firebase_url}/users/{email.replace('.', '_')}.json", 
                 json={"pw": password, "name": name})

def save_chat(email, msgs, cid):
    if not firebase_url or not email: return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}/{cid}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

def get_chat_history(email):
    if not firebase_url or not email: return []
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# --- 3. UI: LOGIN & RESET PASSWORD ---
if "user" not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>Login to KarAI</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔒 Login / Daftar", "🔑 Lupa Password"])
    
    with tab1:
        st.info("Masukkan Email dan Password. Jika email belum terdaftar, otomatis membuat akun baru.")
        email = st.text_input("Email:", placeholder="contoh@gmail.com")
        pw = st.text_input("Password:", type="password")
        
        if st.button("Masuk / Daftar", use_container_width=True):
            if "@" not in email:
                st.error("Format salah! Email wajib menggunakan '@'.")
                st.stop()
            if len(pw) < 4:
                st.error("Password terlalu pendek (minimal 4 karakter).")
                st.stop()
                
            data = get_user_data(email)
            if data:
                if data.get('pw') == pw:
                    st.session_state.user = {"email": email, "name": data.get('name', email.split('@')[0])}
                    st.rerun()
                else: 
                    st.error("Password salah! Gunakan menu Lupa Password jika lupa.")
            else:
                name_default = email.split('@')[0]
                save_user(email, pw, name_default)
                st.session_state.user = {"email": email, "name": name_default}
                st.rerun()

    with tab2:
        st.warning("Gunakan fitur ini jika Anda sudah memiliki akun.")
        email_reset = st.text_input("Email untuk Reset:", placeholder="contoh@gmail.com")
        new_pw = st.text_input("Password Baru:", type="password")
        
        if st.button("Reset Password", use_container_width=True):
            if "@" not in email_reset:
                st.error("Email tidak valid.")
            else:
                data = get_user_data(email_reset)
                if data: 
                    save_user(email_reset, new_pw, data.get('name', email_reset.split('@')[0]))
                    st.success("Password berhasil diperbarui! Silakan Login.")
                else: 
                    st.error("Email belum terdaftar.")
    st.stop()

# --- 4. SESSION INITIALIZATION ---
if "page" not in st.session_state: st.session_state.page = "chat"
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())

# --- 5. SIDEBAR (NAVIGASI & HISTORY) ---
with st.sidebar:
    st.markdown(f"### 👤 Halo, {st.session_state.user['name']}")
    st.divider()
    
    if st.button("💬 Buka Chat", use_container_width=True): st.session_state.page = "chat"; st.rerun()
    if st.button("⚙️ Pengaturan Akun", use_container_width=True): st.session_state.page = "settings"; st.rerun()
    
    st.divider()
    
    if st.session_state.page == "chat":
        if st.button("➕ Chat Baru", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_id = str(uuid.uuid4())
            st.rerun()
        
        # OPSI MODEL MURNI TEKS
        models = [
            "🚀 KGemini", 
            "🧠 KGroq",
            "🎨 KClaude",
            "📞 KGPT"
        ]
        st.session_state.selected_model = st.selectbox("Pilih Mesin AI:", models)
        
        st.divider()
        st.subheader("📜 Riwayat Chat")
        history = get_chat_history(st.session_state.user['email'])
        for cid in history:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(f"Chat: {cid[:6]}...", key=f"btn_{cid}"):
                    url = f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json"
                    res = requests.get(url)
                    st.session_state.messages = res.json() if res.status_code == 200 and res.json() else []
                    st.session_state.chat_id = cid
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{cid}"):
                    requests.delete(f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json")
                    if st.session_state.chat_id == cid: st.session_state.messages = []
                    st.rerun()

    st.divider()
    if st.button("🚪 Logout", use_container_width=True): 
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- 6. PAGES ROUTING ---
if st.session_state.page == "settings":
    st.title("⚙️ Pengaturan Akun")
    st.write(f"**Email Terdaftar:** `{st.session_state.user['email']}`")
    new_name = st.text_input("Ubah Nama Panggilan Anda:", value=st.session_state.user['name'])
    
    if st.button("💾 Simpan Perubahan"):
        curr_data = get_user_data(st.session_state.user['email'])
        pw_to_save = curr_data['pw'] if curr_data else "1234"
        save_user(st.session_state.user['email'], pw_to_save, new_name)
        st.session_state.user['name'] = new_name
        st.success("Nama berhasil diupdate! Silakan kembali ke menu 'Buka Chat'.")

elif st.session_state.page == "chat":
    st.title("KarAI")
    selected_model = st.session_state.get("selected_model", "🚀 KGemini")
    
    # Render History Chat
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    # Input murni teks untuk semua model
    prompt = st.chat_input("Kirim pesan ke KarAI...")

    # Proses AI
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("⏳ KarAI sedang berfikir..."):
            try:
                ai_response = ""
                
                # --- JALUR 1: KGEMINI (GOOGLE) ---
                if "KGemini" in selected_model:
                    genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY", ""))
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(prompt)
                    ai_response = response.text

                # --- JALUR 2: KGROQ (LLAMA 3) ---
                elif "KGroq" in selected_model:
                    if not groq_key: st.error("⚠️ API Key Groq Kosong!"); st.stop()
                    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                    }
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200: ai_response = res.json()["choices"][0]["message"]["content"]
                    else: st.error(f"Groq Error: {res.text}"); st.stop()

                # --- JALUR 3: KCLAUDE (ANTHROPIC) ---
                elif "KClaude" in selected_model:
                    if not anthropic_key: st.error("⚠️ API Key Anthropic Kosong!"); st.stop()
                    headers = {
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                    
                    # Konversi format role untuk Anthropic
                    claude_msgs = []
                    for m in st.session_state.messages:
                        role = "assistant" if m["role"] == "assistant" else "user"
                        claude_msgs.append({"role": role, "content": m["content"]})
                        
                    payload = {
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1024,
                        "messages": claude_msgs
                    }
                    res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                    if res.status_code == 200: ai_response = res.json()["content"][0]["text"]
                    else: st.error(f"Claude Error: {res.text}"); st.stop()

                # --- JALUR 4: KGPT (OPENAI) ---
                elif "KGPT" in selected_model:
                    if not openai_key: st.error("⚠️ API Key OpenAI Kosong!"); st.stop()
                    headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                    }
                    res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200: ai_response = res.json()["choices"][0]["message"]["content"]
                    else: st.error(f"OpenAI Error: {res.text}"); st.stop()
                
                # --- OUTPUT BALASAN ---
                with st.chat_message("assistant"): st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                save_chat(st.session_state.user['email'], st.session_state.messages, st.session_state.chat_id)
                
                st.rerun()
                
            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan API. Detail: {e}")
                if len(st.session_state.messages) > 0:
                    st.session_state.messages.pop()