import streamlit as st
import requests
import uuid
import urllib.parse
import re
import base64

# ============================================================
# 1. SETUP & CSS
# ============================================================
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

    [data-testid="stExpander"] {
        border: 1px dashed rgba(128,128,128,0.3) !important;
        background-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. LOAD API KEYS DARI SECRETS
# ============================================================
firebase_url  = st.secrets.get("FIREBASE_DB_URL",  "")
groq_key      = st.secrets.get("GROQ_API_KEY",      "")   # masih dipake buat KSmart vision
cerebras_key  = st.secrets.get("CEREBRAS_API_KEY",  "")   # daftar di inference.cerebras.ai
sambanova_key = st.secrets.get("SAMBANOVA_API_KEY", "")   # daftar di cloud.sambanova.ai

# ============================================================
# 3. KONFIGURASI MULTI-PROVIDER FALLBACK
#    Urutan: Cerebras (1 juta token/hari) → SambaNova → Groq
# ============================================================
PROVIDERS = [
    {
        "name": "Cerebras",
        "url":  "https://api.cerebras.ai/v1/chat/completions",
        "key":  cerebras_key,
        "models": {
            "basic":   "llama3.1-8b",
            "expert":  "gpt-oss-120b",
            "listen":  "gpt-oss-120b",
            "smart":   "gpt-oss-120b",
            "default": "llama3.1-8b",
        }
    },
    {
        "name": "SambaNova",
        "url":  "https://api.sambanova.ai/v1/chat/completions",
        "key":  sambanova_key,
        "models": {
            "basic":   "Meta-Llama-3.1-8B-Instruct",
            "expert":  "Meta-Llama-3.1-70B-Instruct",
            "listen":  "Meta-Llama-3.1-70B-Instruct",
            "smart":   "Meta-Llama-3.1-70B-Instruct",
            "default": "Meta-Llama-3.1-8B-Instruct",
        }
    },
    {
        "name": "Groq",
        "url":  "https://api.groq.com/openai/v1/chat/completions",
        "key":  groq_key,
        "models": {
            "basic":   "llama-3.1-8b-instant",
            "expert":  "llama-3.3-70b-versatile",
            "listen":  "llama-3.3-70b-versatile",
            "smart":   "llama-3.3-70b-versatile",
            "default": "llama-3.1-8b-instant",
        }
    },
]

# ============================================================
# 4. FUNGSI DATABASE (FIREBASE)
# ============================================================
def get_user_data(email):
    if not firebase_url:
        return None
    res = requests.get(f"{firebase_url}/users/{email.replace('.', '_')}.json")
    return res.json() if res.status_code == 200 else None

def save_user(email, password, name, is_premium=False):
    if not firebase_url:
        return
    requests.put(
        f"{firebase_url}/users/{email.replace('.', '_')}.json",
        json={"pw": password, "name": name, "premium": is_premium}
    )

def save_chat(email, msgs, cid):
    if not firebase_url or not email:
        return
    url = f"{firebase_url}/chats/{email.replace('.', '_')}/{cid}.json"
    requests.put(url, json=[{"role": m["role"], "content": m["content"]} for m in msgs])

def get_chat_history(email):
    if not firebase_url or not email:
        return []
    url = f"{firebase_url}/chats/{email.replace('.', '_')}.json?shallow=true"
    res = requests.get(url)
    return list(res.json().keys()) if res.status_code == 200 and res.json() else []

# ============================================================
# 5. FUNGSI AI: MULTI-PROVIDER FALLBACK
# ============================================================
def detect_mode(selected_model_str):
    """Mapping nama model di UI → key mode untuk PROVIDERS."""
    if "KBasic"  in selected_model_str: return "basic"
    if "KExpert" in selected_model_str: return "expert"
    if "KListen" in selected_model_str: return "listen"
    if "KSmart"  in selected_model_str: return "smart"
    return "default"

def call_ai_fallback(messages_payload, selected_model_str):
    """
    Coba Cerebras dulu (1 juta token/hari gratis, ultra cepat),
    lalu SambaNova, lalu Groq sebagai last resort.
    Kalau kena 429 rate limit atau timeout → otomatis pindah ke provider berikutnya.
    """
    mode_key = detect_mode(selected_model_str)
    tried    = []

    for p in PROVIDERS:
        if not p["key"]:
            continue  # skip provider yang keynya kosong / belum diisi

        model_name = p["models"].get(mode_key, p["models"]["default"])
        tried.append(p["name"])

        try:
            headers = {
                "Authorization": f"Bearer {p['key']}",
                "Content-Type":  "application/json",
            }
            payload = {
                "model":    model_name,
                "messages": messages_payload,
            }
            res = requests.post(p["url"], headers=headers, json=payload, timeout=30)

            if res.status_code == 200:
                st.caption(f"✅ Dijawab oleh: **{p['name']}** ({model_name})")
                return res.json()["choices"][0]["message"]["content"]

            elif res.status_code == 429:
                # Rate limit → coba provider berikutnya
                st.toast(f"⚠️ {p['name']} lagi penuh, pindah ke cadangan...", icon="🔄")
                continue

            else:
                # Error lain → tetap lanjut ke provider berikutnya
                continue

        except requests.exceptions.Timeout:
            st.toast(f"⏱️ {p['name']} timeout, coba yang lain...", icon="🔄")
            continue
        except Exception:
            continue

    # Kalau semua provider gagal
    return (
        f"❌ Semua server AI lagi sibuk (sudah dicoba: {', '.join(tried)}). "
        "Tunggu sebentar lalu coba lagi ya!"
    )

# ============================================================
# 6. HELPER: RENDER PESAN AI (SEMBUNYIKAN TAG <think>)
# ============================================================
def render_ai_message(text):
    match = re.search(r'<think>(.*?)</think>', text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        think_text = match.group(1).strip()
        main_text  = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
        if think_text:
            with st.expander("💭 Proses Berpikir..."):
                st.markdown(f"*{think_text}*")
        st.markdown(main_text)
    else:
        st.markdown(text)

# ============================================================
# 7. UI: LOGIN & REGISTER
# ============================================================
if "user" not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>Login to KarAI</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔒 Login / Daftar", "🔑 Lupa Password"])

    with tab1:
        st.info("Masukkan Email dan Password. Jika email belum terdaftar, otomatis membuat akun baru.")
        email = st.text_input("Email:", placeholder="contoh@gmail.com")
        pw    = st.text_input("Password:", type="password")

        if st.button("Masuk / Daftar", use_container_width=True):
            if "@" not in email:
                st.error("Format salah! Email wajib menggunakan '@'.")
                st.stop()
            if len(pw) < 4:
                st.error("Password terlalu pendek (minimal 4 karakter).")
                st.stop()

            data = get_user_data(email)
            if data:
                if data.get("pw") == pw:
                    st.session_state.user = {
                        "email":   email,
                        "name":    data.get("name", email.split("@")[0]),
                        "premium": data.get("premium", False),
                    }
                    st.rerun()
                else:
                    st.error("Password salah! Gunakan menu Lupa Password jika lupa.")
            else:
                name_default = email.split("@")[0]
                save_user(email, pw, name_default, False)
                st.session_state.user = {
                    "email":   email,
                    "name":    name_default,
                    "premium": False,
                }
                st.rerun()

    with tab2:
        st.warning("Gunakan fitur ini jika Anda sudah memiliki akun.")
        email_reset = st.text_input("Email untuk Reset:", placeholder="contoh@gmail.com")
        new_pw      = st.text_input("Password Baru:", type="password")

        if st.button("Reset Password", use_container_width=True):
            if "@" not in email_reset:
                st.error("Email tidak valid.")
            else:
                data = get_user_data(email_reset)
                if data:
                    save_user(
                        email_reset, new_pw,
                        data.get("name", email_reset.split("@")[0]),
                        data.get("premium", False)
                    )
                    st.success("Password berhasil diperbarui! Silakan Login.")
                else:
                    st.error("Email belum terdaftar.")
    st.stop()

# ============================================================
# 8. INISIALISASI SESSION STATE
# ============================================================
if "page"         not in st.session_state: st.session_state.page         = "chat"
if "messages"     not in st.session_state: st.session_state.messages     = []
if "chat_id"      not in st.session_state: st.session_state.chat_id      = str(uuid.uuid4())
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# ============================================================
# 9. SIDEBAR
# ============================================================
with st.sidebar:
    status_badge = "🌟 VIP" if st.session_state.user.get("premium", False) else "👤"
    st.markdown(f"### {status_badge} Halo, {st.session_state.user['name']}")
    st.divider()

    if st.button("💬 Buka Chat",        use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()
    if st.button("⚙️ Pengaturan Akun", use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()

    st.divider()

    if st.session_state.page == "chat":
        if st.button("➕ Chat Baru", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_id  = str(uuid.uuid4())
            st.rerun()

        # Model gratis
        models = ["🚀 KBasic", "🧠 KExpert", "👂 KListen"]
        # Tambahan kalau premium
        if st.session_state.user.get("premium", False):
            models.extend(["🎨 KCreative", "🔮 KSmart"])

        st.session_state.selected_model = st.selectbox("Pilih Mesin AI:", models)

        # Upload gambar hanya muncul kalau KSmart
        if "KSmart" in st.session_state.selected_model:
            uploaded_file = st.file_uploader(
                "Upload Foto (Khusus KSmart):",
                type=["png", "jpg", "jpeg"],
                key=st.session_state.uploader_key
            )
        else:
            uploaded_file = None

        st.divider()
        st.subheader("📜 Riwayat Chat")
        history = get_chat_history(st.session_state.user["email"])
        for cid in history:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(f"Chat: {cid[:6]}...", key=f"btn_{cid}"):
                    url = f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json"
                    res = requests.get(url)
                    st.session_state.messages = res.json() if res.status_code == 200 and res.json() else []
                    st.session_state.chat_id  = cid
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{cid}"):
                    requests.delete(
                        f"{firebase_url}/chats/{st.session_state.user['email'].replace('.', '_')}/{cid}.json"
                    )
                    if st.session_state.chat_id == cid:
                        st.session_state.messages = []
                    st.rerun()

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================
# 10. HALAMAN: PENGATURAN AKUN
# ============================================================
if st.session_state.page == "settings":
    st.title("⚙️ Pengaturan Akun")
    st.write(f"**Email Terdaftar:** `{st.session_state.user['email']}`")
    new_name = st.text_input("Ubah Nama Panggilan Anda:", value=st.session_state.user["name"])
    st.divider()

    st.subheader("🔑 Akses Fitur Premium")
    secret_token = st.text_input("Masukkan Token Khusus Premium:", type="password")

    if st.button("💾 Simpan Perubahan"):
        curr_data  = get_user_data(st.session_state.user["email"])
        pw_to_save = curr_data["pw"] if curr_data else "1234"
        is_premium = curr_data.get("premium", False) if curr_data else False

        if secret_token == "kontolodonmegalodonshark":
            is_premium = True
            st.success("🎉 Token Valid! Fitur KCreative dan KSmart berhasil dibuka.")
        elif secret_token != "":
            st.error("❌ Token rahasia salah.")

        save_user(st.session_state.user["email"], pw_to_save, new_name, is_premium)
        st.session_state.user["name"]    = new_name
        st.session_state.user["premium"] = is_premium
        st.success("Data akun berhasil diupdate! Silakan kembali ke menu 'Buka Chat'.")

# ============================================================
# 11. HALAMAN: CHAT UTAMA
# ============================================================
elif st.session_state.page == "chat":
    st.title("KarAI")
    selected_model = st.session_state.get("selected_model", "🚀 KBasic")

    # Tampilkan history percakapan
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                render_ai_message(m["content"])
            elif "image_url" in m["content"]:
                st.markdown("📷 *[Gambar terkirim]*")
            else:
                st.markdown(m["content"])

    # Input user
    if prompt := st.chat_input("Kirim pesan ke KarAI..."):

        # Tampilkan pesan user di layar
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                st.image(uploaded_file, width=200)

        # Simpan ke history (teks saja)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("⏳ KarAI sedang berpikir..."):
            try:
                ai_response = ""

                # --------------------------------------------------
                # MESIN 1: KCREATIVE → generate gambar via Pollinations
                # --------------------------------------------------
                if "KCreative" in selected_model:
                    encoded_prompt = urllib.parse.quote(prompt)
                    img_id         = uuid.uuid4().int & 100000
                    image_url      = (
                        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                        f"?width=512&height=512&seed={img_id}&nologo=true"
                    )
                    ai_response = (
                        f"Berikut adalah hasil gambar untuk perintah: **{prompt}**\n\n"
                        f"![Generated Image]({image_url})"
                    )

                # --------------------------------------------------
                # MESIN 2: KSMART + FOTO → Groq Vision (satu-satunya
                #          provider yang support image input gratis)
                # --------------------------------------------------
                elif "KSmart" in selected_model and uploaded_file:
                    if not groq_key:
                        st.error("⚠️ GROQ_API_KEY belum diisi di Secrets! KSmart + foto butuh Groq.")
                        st.session_state.messages.pop()
                        st.stop()

                    base64_image   = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                    image_url_data = f"data:image/jpeg;base64,{base64_image}"

                    messages_payload = []
                    for i, m in enumerate(st.session_state.messages):
                        if i == len(st.session_state.messages) - 1:
                            # Pesan terakhir (yang baru): sertakan gambar
                            messages_payload.append({
                                "role": "user",
                                "content": [
                                    {"type": "text",      "text": m["content"]},
                                    {"type": "image_url", "image_url": {"url": image_url_data}},
                                ],
                            })
                        else:
                            messages_payload.append({"role": m["role"], "content": m["content"]})

                    headers = {
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type":  "application/json",
                    }
                    res = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json={"model": "meta-llama/llama-4-scout-17b-16e-instruct", "messages": messages_payload},
                        timeout=30,
                    )

                    if res.status_code == 200:
                        ai_response = res.json()["choices"][0]["message"]["content"]
                    else:
                        ai_response = f"❌ Error Groq Vision: {res.text}"

                # --------------------------------------------------
                # MESIN 3: SEMUA MODE TEKS (KBasic, KExpert, KListen,
                #          KSmart tanpa foto) → Multi-provider fallback
                # --------------------------------------------------
                else:
                    messages_payload = []

                    # System prompt khusus KListen
                    if "KListen" in selected_model:
                        messages_payload.append({
                            "role": "system",
                            "content": (
                                "Kamu adalah KListen, AI teman curhat. Aturan mutlak perilakumu: "
                                "1. Jika pengguna bersedih, galau, atau curhat baik-baik, balaslah dengan "
                                "sangat lembut, menenangkan, dan penuh empati layaknya sahabat. "
                                "2. JIKA pengguna ngegas, berkata kasar, toxic, atau maki-maki duluan, "
                                "KAMU WAJIB MERESPON DENGAN SANGAT GALAK, NGEGAS, DAN MAKI-MAKI BALIK "
                                "TANPA AMPUN. "
                                "Jangan bersikap kaku atau formal, gunakan bahasa gaul Indonesia "
                                "sehari-hari (lu/gw, anjir, astaga, dll)."
                            ),
                        })

                    # Mapping seluruh history ke payload
                    for m in st.session_state.messages:
                        messages_payload.append({"role": m["role"], "content": m["content"]})

                    # Panggil dengan fallback otomatis
                    ai_response = call_ai_fallback(messages_payload, selected_model)

                # Tampilkan & simpan balasan AI
                with st.chat_message("assistant"):
                    render_ai_message(ai_response)

                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                save_chat(
                    st.session_state.user["email"],
                    st.session_state.messages,
                    st.session_state.chat_id,
                )
                st.session_state.uploader_key = str(uuid.uuid4())
                st.rerun()

            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan. Detail: {e}")
                if st.session_state.messages:
                    st.session_state.messages.pop()