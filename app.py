import streamlit as st
import requests
import uuid
import urllib.parse
import re
import base64

# --- 1. SETUP & CSS (TEMA AMAN, CHAT KANAN-KIRI, & NO SPINNER ICON) ---
st.set_page_config(page_title="KarAI OS", page_icon="🤖", layout="centered")

st.markdown("""
<style>
    /* Desain Chat: User di Kanan, AI di Kiri */
    .stChatMessage { padding: 10px; border-radius: 10px; margin-bottom: 15px; }
    
    /* Modifikasi Chat Bubble User */
    [data-testid="stChatMessageUser"] { 
        background-color: rgba(33, 150, 243, 0.1); 
        flex-direction: row-reverse; 
    }
    [data-testid="stChatMessageUser"] > div { text-align: right; }
    
    /* Sembunyikan icon avatar default biar lebih bersih */
    [data-testid="stChatMessageAvatar"] { display: none; }
    
    /* Hapus icon jam pasir/loading default Streamlit */
    [data-testid="stSpinner"] > div > div { display: none !important; }
    [data-testid="stSpinner"] { background-color: transparent !important; color: inherit !important; }
    
    /* Percantik Expander untuk Proses Mikir */
    [data-testid="stExpander"] {
        border: 1px dashed rgba(128,128,128,0.3) !important;
        background-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")
groq_key = st.secrets.get("GROQ_API_KEY", "")

# --- 2. LOGIKA DATABASE (FIREBASE) ---
def get_user_data(email):
    if not firebase_url: return None
    res = requests.get(f"{firebase_url}/users/{email.replace('.', '_')}.json")
    return res.json() if res.status_code == 200 else None

def save_user(email, password, name, is_premium=False):
    if not firebase_url: return
    requests.put(f"{firebase_url}/users/{email.replace('.', '_')}.json", 
                 json={"pw": password, "name": name, "premium": is_premium})

def save_chat(email, msgs, cid):
    if not firebase_url or not email: return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}/{cid}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

def get_chat_history(email):
    if not firebase_url or not email: return []
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# --- 3. HELPER UNTUK RENDER PESAN AI (SEMBUNYIKAN <THINK>) ---
def render_ai_message(text):
    match = re.search(r'<think>(.*?)</think>', text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        think_text = match.group(1).strip()
        main_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
        
        if think_text:
            with st.expander("💭 Proses Berpikir..."):
                st.markdown(f"*{think_text}*")
        
        st.markdown(main_text)
    else:
        st.markdown(text)

# --- 4. UI: LOGIN & REGISTER ---
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
                    st.session_state.user = {
                        "email": email, 
                        "name": data.get('name', email.split('@')[0]),
                        "premium": data.get('premium', False)
                    }
                    st.rerun()
                else: 
                    st.error("Password salah! Gunakan menu Lupa Password jika lupa.")
            else:
                name_default = email.split('@')[0]
                save_user(email, pw, name_default, False)
                st.session_state.user = {"email": email, "name": name_default, "premium": False}
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
                    save_user(email_reset, new_pw, data.get('name', email_reset.split('@')[0]), data.get('premium', False))
                    st.success("Password berhasil diperbarui! Silakan Login.")
                else: 
                    st.error("Email belum terdaftar.")
    st.stop()

# --- 5. INISIALISASI SESI ---
if "page" not in st.session_state: st.session_state.page = "chat"
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# --- 6. SIDEBAR (NAVIGASI, HISTORY, & MODEL OPTIONS) ---
with st.sidebar:
    status_badge = "🌟 VIP" if st.session_state.user.get('premium', False) else "👤"
    st.markdown(f"### {status_badge} Halo, {st.session_state.user['name']}")
    st.divider()
    
    if st.button("💬 Buka Chat", use_container_width=True): st.session_state.page = "chat"; st.rerun()
    if st.button("⚙️ Pengaturan Akun", use_container_width=True): st.session_state.page = "settings"; st.rerun()
    
    st.divider()
    
    if st.session_state.page == "chat":
        if st.button("➕ Chat Baru", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_id = str(uuid.uuid4())
            st.rerun()
        
        # MODEL DEFAULT (KLISTEN SEKARANG GRATIS)
        models = ["🚀 KBasic", "🧠 KExpert", "👂 KListen"]
        
        # MODEL TAMBAHAN JIKA STATUS PREMIUM AKTIF
        if st.session_state.user.get('premium', False):
            models.extend(["🎨 KCreative", "🔮 KSmart"])
        
        st.session_state.selected_model = st.selectbox("Pilih Mesin AI:", models)
        
        # FITUR UPLOAD GAMBAR KHUSUS BUAT KSMART
        if "KSmart" in st.session_state.selected_model:
            uploaded_file = st.file_uploader("Upload Foto (Khusus KSmart):", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
        else:
            uploaded_file = None
            
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

# --- 7. PAGES ROUTING ---
if st.session_state.page == "settings":
    st.title("⚙️ Pengaturan Akun")
    st.write(f"**Email Terdaftar:** `{st.session_state.user['email']}`")
    new_name = st.text_input("Ubah Nama Panggilan Anda:", value=st.session_state.user['name'])
    st.divider()
    
    st.subheader("🔑 Akses Fitur Premium")
    secret_token = st.text_input("Masukkan Token Khusus Premium:", type="password")
    
    if st.button("💾 Simpan Perubahan"):
        curr_data = get_user_data(st.session_state.user['email'])
        pw_to_save = curr_data['pw'] if curr_data else "1234"
        is_premium = curr_data.get('premium', False) if curr_data else False
        
        if secret_token == "kontolodonmegalodonshark":
            is_premium = True
            st.success("🎉 Token Valid! Fitur KCreative dan KSmart berhasil dibuka.")
        elif secret_token != "":
            st.error("❌ Token rahasia salah.")
            
        save_user(st.session_state.user['email'], pw_to_save, new_name, is_premium)
        st.session_state.user['name'] = new_name
        st.session_state.user['premium'] = is_premium
        st.success("Data akun berhasil diupdate! Silakan kembali ke menu 'Buka Chat'.")

elif st.session_state.page == "chat":
    st.title("KarAI")
    selected_model = st.session_state.get("selected_model", "🚀 KBasic")
    
    # Tampilkan percakapan lama
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): 
            if m["role"] == "assistant":
                render_ai_message(m["content"])
            elif "image_url" in m["content"]:
                st.markdown("📷 *[Gambar terkirim]*")
            else:
                st.markdown(m["content"])

    # Input murni teks
    if prompt := st.chat_input("Kirim pesan ke KarAI..."):
        # Tampilkan prompt user di layar
        with st.chat_message("user"): 
            st.markdown(prompt)
            if 'uploaded_file' in locals() and uploaded_file:
                st.image(uploaded_file, width=200)

        # Simpan ke session_state history (hanya teksnya saja agar rapi)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.spinner("⏳ KarAI sedang berfikir..."):
            try:
                ai_response = ""
                
                # --- MESIN 1: KCREATIVE (IMAGE GENERATOR) ---
                if "KCreative" in selected_model:
                    encoded_prompt = urllib.parse.quote(prompt)
                    img_id = uuid.uuid4().int & 100000
                    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={img_id}&nologo=true"
                    ai_response = f"Berikut adalah hasil gambar untuk perintah: **{prompt}**\n\n![Generated Image]({image_url})"
                
                # --- MESIN 2: TEXT & VISION PROCESSING VIA GROQ ---
                else:
                    if not groq_key:
                        st.error("⚠️ API Key Groq belum dipasang di Secrets!")
                        st.session_state.messages.pop()
                        st.stop()
                    
                    # Tentukan Target Model
                    if "KBasic" in selected_model:
                        model_target = "llama-3.1-8b-instant"
                    elif "KExpert" in selected_model:
                        model_target = "llama-3.3-70b-versatile"
                    elif "KSmart" in selected_model:
                        model_target = "llama-3.2-90b-vision-preview" # MODEL VISION PALING OP DI GROQ
                    elif "KListen" in selected_model:
                        model_target = "llama-3.3-70b-versatile" 
                    else:
                        model_target = "llama-3.1-8b-instant"
                        
                    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                    
                    # Bangun Payload Chat
                    messages_payload = []
                    
                    # SYSTEM PROMPT BUAT KLISTEN
                    if "KListen" in selected_model:
                        messages_payload.append({
                            "role": "system",
                            "content": "Kamu adalah KListen, AI teman curhat. Aturan mutlak perilakumu: 1. Jika pengguna bersedih, galau, atau curhat baik-baik, balaslah dengan sangat lembut, menenangkan, dan penuh empati layaknya sahabat. 2. JIKA pengguna ngegas, berkata kasar, toxic, atau maki-maki duluan, KAMU WAJIB MERESPON DENGAN SANGAT GALAK, NGEGAS, DAN MAKI-MAKI BALIK TANPA AMPUN. Jangan bersikap kaku atau formal, gunakan bahasa gaul Indonesia sehari-hari (lu/gw, anjir, astaga, dll)."
                        })
                    
                    # Mapping History ke Payload API
                    for i, m in enumerate(st.session_state.messages):
                        # Khusus untuk KSMART: Kalau ini chat terakhir dan ada gambar di-upload
                        if i == len(st.session_state.messages) - 1 and "KSmart" in selected_model and uploaded_file:
                            base64_image = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
                            image_url = f"data:image/jpeg;base64,{base64_image}"
                            
                            messages_payload.append({
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": m["content"]},
                                    {"type": "image_url", "image_url": {"url": image_url}}
                                ]
                            })
                        else:
                            # Teks biasa untuk chat history sebelumnya / model lain
                            messages_payload.append({"role": m["role"], "content": m["content"]})
                    
                    payload = {
                        "model": model_target,
                        "messages": messages_payload
                    }
                    
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    
                    if res.status_code == 200:
                        ai_response = res.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"Groq API Error: {res.text}")
                        st.session_state.messages.pop()
                        st.stop()
                
                # Tampilkan balasan AI
                with st.chat_message("assistant"): 
                    render_ai_message(ai_response)
                
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                save_chat(st.session_state.user['email'], st.session_state.messages, st.session_state.chat_id)
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()
                
            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan API. Detail: {e}")
                if len(st.session_state.messages) > 0:
                    st.session_state.messages.pop()