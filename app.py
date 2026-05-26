import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
import uuid

# --- 1. SETUP & CSS ---
st.set_page_config(page_title="KarAI", page_icon="K", layout="centered")

st.markdown("""
<style>
    .stChatMessage { padding: 10px; border-radius: 10px; margin-bottom: 15px; }
    [data-testid="stChatMessageUser"] { 
        background-color: rgba(33, 150, 243, 0.1); 
        flex-direction: row-reverse; 
    }
    [data-testid="stChatMessageUser"] > div { text-align: right; }
    [data-testid="stChatMessageAvatar"] { display: none; }
</style>
""", unsafe_allow_html=True)

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")

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
    st.markdown("<h1 style='text-align: center;'>Portal KarAI</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔒 Login / Daftar", "🔑 Lupa Password"])
    
    with tab1:
        st.info("Masukkan Email dan Password. Jika email belum terdaftar, sistem akan otomatis membuat akun baru.")
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
                    st.error("Password salah! Silakan gunakan menu Lupa Password jika lupa.")
            else:
                name_default = email.split('@')[0]
                save_user(email, pw, name_default)
                st.session_state.user = {"email": email, "name": name_default}
                st.rerun()

    with tab2:
        st.warning("Gunakan fitur ini hanya jika Anda sudah pernah membuat akun sebelumnya.")
        email_reset = st.text_input("Email untuk Reset:", placeholder="contoh@gmail.com")
        new_pw = st.text_input("Password Baru:", type="password")
        
        if st.button("Reset Password", use_container_width=True):
            if "@" not in email_reset:
                st.error("Email tidak valid.")
            else:
                data = get_user_data(email_reset)
                if data: 
                    save_user(email_reset, new_pw, data.get('name', email_reset.split('@')[0]))
                    st.success("Password berhasil diperbarui! Silakan kembali ke tab Login.")
                else: 
                    st.error("Email belum terdaftar di database.")
    st.stop()

# --- 4. SESSION INITIALIZATION ---
if "page" not in st.session_state: st.session_state.page = "chat"
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# --- 5. SIDEBAR ---
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
        
        # GROQ UNLIMITED SEKARANG DIBUKA BUAT SEMUA ORANG!
        models = [
            "🚀 Karai Unlimited (Groq Llama 3)", 
            "⚡ Karai Basic (Gemini)", 
            "🧠 Karai Expert (Gemini)"
        ]
        
        st.session_state.selected_model = st.selectbox("Pilih Model:", models)
        uploaded_file = st.file_uploader("Upload Foto (Khusus Gemini):", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
        
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
        st.success("Nama berhasil diupdate! Silakan kembali ke menu 'Buka Chat' di sidebar.")

elif st.session_state.page == "chat":
    st.title("KarAI")
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Kirim pesan ke KarAI..."):
        img = Image.open(uploaded_file) if 'uploaded_file' in locals() and uploaded_file else None
        selected_model = st.session_state.get("selected_model", "")
        
        if img and "Unlimited" in selected_model:
            st.error("⚠️ Model 'Unlimited (Groq)' hanya untuk Teks. Ubah ke Gemini di sidebar jika ingin kirim gambar.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): 
            st.markdown(prompt)
            if img: st.image(img, width=200)
        
        with st.spinner("⏳ KarAI sedang berpikir..."):
            try:
                ai_response = ""
                
                # --- MESIN 1: GROQ UNLIMITED ---
                if "Unlimited" in selected_model:
                    groq_key = st.secrets.get("GROQ_API_KEY", "")
                    if not groq_key:
                        st.error("⚠️ API Key Groq belum dipasang di Secrets Streamlit Cloud!")
                        st.session_state.messages.pop() 
                        st.stop()
                        
                    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]}
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    
                    if res.status_code == 200:
                        ai_response = res.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"Groq API Error: {res.text}")
                        st.session_state.messages.pop()
                        st.stop()

                # --- MESIN 2: GEMINI ---
                else:
                    genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY", ""))
                    # Fix: Google mematikan gemini-pro, kita pakai 1.5 flash & pro murni
                    gemini_model = "gemini-1.5-flash" if "Basic" in selected_model else "gemini-1.5-pro"
                    
                    model = genai.GenerativeModel(gemini_model)
                    payload = [prompt, img] if img else [prompt]
                    response = model.generate_content(payload)
                    ai_response = response.text
                
                with st.chat_message("assistant"): st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                save_chat(st.session_state.user['email'], st.session_state.messages, st.session_state.chat_id)
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()
                
            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan API. Detail: {e}")
                if len(st.session_state.messages) > 0:
                    st.session_state.messages.pop()