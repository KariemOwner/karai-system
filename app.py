import streamlit as st
from PIL import Image
import requests
import uuid
import urllib.parse
import json
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
    
    /* HAPUS ICON JAM PASIR SAAT LOADING */
    [data-testid="stSpinner"] > div > div { display: none !important; }
    [data-testid="stSpinner"] { background-color: transparent !important; color: inherit !important; }
</style>
""", unsafe_allow_html=True)

firebase_url = st.secrets.get("FIREBASE_DB_URL", "")
groq_key = st.secrets.get("GROQ_API_KEY", "")

# --- 2. DATABASE LOGIC (FIREBASE) ---
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

# --- 3. UI: LOGIN & RESET PASSWORD (UBAH TEKS PORTAL) ---
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

    # FIX TYPO SYNTAX ERROR DI SINI
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

# --- 4. SESSION INITIALIZATION & FALLBACK FOR VOICE MODE ---
if "page" not in st.session_state: st.session_state.page = "chat"
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())
if "last_audio_bytes" not in st.session_state: st.session_state.last_audio_bytes = None
if "speak_text" not in st.session_state: st.session_state.speak_text = ""

# --- 5. SIDEBAR (NAVIGASI, HISTORY, & PREMIUM LOGIC) ---
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
            st.session_state.last_audio_bytes = None
            st.rerun()
        
        models = [
            "🚀 Karai Basic (Groq Llama 8B)", 
            "🧠 Karai Expert (Groq Llama 70B)",
            "🎨 Karai Creative (Image Generator)",
            "📞 Karai Voice (Voice Mode)"
        ]
        
        if st.session_state.user.get('premium', False):
            models.extend([
                "🔥 Karai Premium Vision (Groq Llama Vision)", 
                "🌟 Karai Premium X (Groq Llama 70B)"
            ])
        
        st.session_state.selected_model = st.selectbox("Pilih Model Engine:", models)
        
        if "Premium Vision" in st.session_state.selected_model:
            uploaded_file = st.file_uploader("Upload Foto:", type=['png', 'jpg', 'jpeg'], key=st.session_state.uploader_key)
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
                    st.session_state.last_audio_bytes = None
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
    st.divider()
    
    st.subheader("🔑 Akses Premium")
    secret_token = st.text_input("Masukkan Token Khusus:", type="password")
    
    if st.button("💾 Simpan Perubahan"):
        curr_data = get_user_data(st.session_state.user['email'])
        pw_to_save = curr_data['pw'] if curr_data else "1234"
        is_premium = curr_data.get('premium', False) if curr_data else False
        
        if secret_token == "kontolodonmegalodonshark":
            is_premium = True
            st.success("🎉 Token Valid! Akses KarAI Premium & Fitur Upload Gambar berhasil dibuka.")
        elif secret_token != "":
            st.error("❌ Token rahasia salah.")
            
        save_user(st.session_state.user['email'], pw_to_save, new_name, is_premium)
        st.session_state.user['name'] = new_name
        st.session_state.user['premium'] = is_premium
        st.success("Data akun berhasil diupdate! Silakan kembali ke menu 'Buka Chat'.")

elif st.session_state.page == "chat":
    st.title("KarAI")
    selected_model = st.session_state.get("selected_model", "🚀 Karai Basic (Groq Llama 8B)")
    
    if st.session_state.get("speak_text"):
        clean_text = st.session_state.speak_text.replace("'", "\\'").replace("\n", " ").replace('"', '\\"')
        st.components.v1.html(f"""
            <script>
                var msg = new SpeechSynthesisUtterance('{clean_text}');
                msg.lang = 'id-ID';
                window.speechSynthesis.speak(msg);
            </script>
        """, height=0)
        st.session_state.speak_text = ""
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    prompt = None
    if "Voice" in selected_model:
        st.warning("🎙️ Mode Voice Aktif: Silakan rekam suara Anda.")
        audio_file = st.audio_input("Rekam:")
        
        if audio_file:
            audio_bytes = audio_file.getvalue()
            if st.session_state.last_audio_bytes != audio_bytes:
                st.session_state.last_audio_bytes = audio_bytes
                
                with st.spinner("⏳ KarAI sedang berfikir..."):
                    try:
                        headers = {"Authorization": f"Bearer {groq_key}"}
                        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
                        data = {"model": "whisper-large-v3", "language": "id"}
                        res = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=headers, files=files, data=data)
                        
                        if res.status_code == 200:
                            prompt = res.json().get("text", "")
                        else:
                            st.error(f"Gagal memproses audio: {res.text}")
                    except Exception as e:
                        st.error(f"Error STT: {e}")
            else:
                prompt = None 
    else:
        prompt = st.chat_input("Kirim pesan ke KarAI...")

    if prompt:
        img = Image.open(uploaded_file) if ('uploaded_file' in locals() and uploaded_file) else None
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): 
            st.markdown(prompt)
            if img: st.image(img, width=200)
        
        with st.spinner("⏳ KarAI sedang berfikir..."):
            try:
                ai_response = ""
                
                # --- MESIN 1: PREMIUM VISION (MENGGUNAKAN GROQ VISION AGAR TIDAK ADA ERROR GEMINI) ---
                if "Premium Vision" in selected_model:
                    if not groq_key:
                        st.error("⚠️ API Key Groq belum dipasang di Secrets!")
                        st.session_state.messages.pop()
                        st.stop()
                        
                    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                    
                    if uploaded_file:
                        base64_image = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
                        image_url = f"data:image/jpeg;base64,{base64_image}"
                        
                        payload = {
                            "model": "llama-3.2-11b-vision-preview",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {"type": "image_url", "image_url": {"url": image_url}}
                                    ]
                                }
                            ]
                        }
                    else:
                        payload = {
                            "model": "llama-3.3-70b-versatile",
                            "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                        }
                    
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    
                    if res.status_code == 200:
                        ai_response = res.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"Groq API Error: {res.text}")
                        st.session_state.messages.pop()
                        st.stop()

                # --- MESIN 2: CREATIVE (IMAGE GENERATION) ---
                elif "Creative" in selected_model:
                    encoded_prompt = urllib.parse.quote(prompt)
                    img_id = uuid.uuid4().int & 100000
                    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={img_id}&nologo=true"
                    ai_response = f"Berikut adalah gambar untuk: **{prompt}**\n\n![Generated Image]({image_url})"
                
                # --- MESIN 3: BASIC, EXPERT, & VOICE (GROQ LLAMA) ---
                else:
                    if not groq_key:
                        st.error("⚠️ API Key Groq belum dipasang di Secrets!")
                        st.session_state.messages.pop()
                        st.stop()
                        
                    model_target = "llama-3.1-8b-instant" if "Basic" in selected_model else "llama-3.3-70b-versatile"
                        
                    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": model_target,
                        "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                    }
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    
                    if res.status_code == 200:
                        ai_response = res.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"Groq API Error: {res.text}")
                        st.session_state.messages.pop()
                        st.stop()
                
                # Cetak Balasan
                with st.chat_message("assistant"): st.markdown(ai_response)
                
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                save_chat(st.session_state.user['email'], st.session_state.messages, st.session_state.chat_id)
                
                if "Voice" in selected_model:
                    st.session_state.speak_text = ai_response
                
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()
                
            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan API. Detail: {e}")
                if len(st.session_state.messages) > 0:
                    st.session_state.messages.pop()