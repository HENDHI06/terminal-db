import google.generativeai as genai

# ... (KODE ANDA YANG SEBELUMNYA TETAP ADA DI ATAS SINI) ...

def render_asisten_ai(user_now, role):
    st.markdown(f"<h2 class='gradient-text'>Asisten Keuangan Cerdas (AI)</h2>", unsafe_allow_html=True)
    
    tab_doc, tab_chat = st.tabs(["🩺 DOKTER PORTOFOLIO", "💬 CHATBOT PENASIHAT"])
    
    # ---------------------------------------------------------
    # TAB 1: DOKTER PORTOFOLIO (AUTO-REBALANCING)
    # ---------------------------------------------------------
    with tab_doc:
        st.markdown("### Audit Kesehatan Portofolio Anda")
        st.caption("AI akan memindai dompet Anda untuk mendeteksi risiko konsentrasi yang berbahaya.")
        
        if st.button("Mulai Audit Kesehatan Keuangan", use_container_width=True):
            with st.spinner("Memindai sektor aset di dompet Anda..."):
                df_p = get_user_portfolio(user_now, role)
                
                if df_p.empty:
                    st.warning("Dompet Anda masih kosong. Silakan beli beberapa aset di menu Dompet Trading terlebih dahulu.")
                else:
                    # Menghitung estimasi total uang yang dimasukkan (Modal)
                    def hitung_modal_idr(row):
                        is_cr = is_crypto_ticker(row['ticker'])
                        pengali = 1 if is_cr else 100
                        return float(row['buy_price']) * float(row['lots']) * pengali
                    
                    df_p['Modal_IDR'] = df_p.apply(hitung_modal_idr, axis=1)
                    
                    # Memetakan ke Sektor
                    df_p['Sektor'] = df_p['ticker'].apply(get_sector)
                    
                    # Mengelompokkan berdasarkan sektor
                    distribusi = df_p.groupby('Sektor')['Modal_IDR'].sum().reset_index()
                    total_semua_modal = distribusi['Modal_IDR'].sum()
                    distribusi['Persentase'] = (distribusi['Modal_IDR'] / total_semua_modal) * 100
                    
                    # Membuat visualisasi Pie Chart
                    fig_pie = px.pie(distribusi, values='Modal_IDR', names='Sektor', title='Distribusi Sektor Portofolio Anda',
                                     color_discrete_sequence=px.colors.sequential.Teal)
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Logika Peringatan (Auto-Rebalancing Rule)
                    sektor_terbesar = distribusi.loc[distribusi['Persentase'].idxmax()]
                    
                    st.markdown("---")
                    if sektor_terbesar['Persentase'] >= 70:
                        st.error(f"⚠️ **STATUS: BAHAYA (RISIKO TINGGI)**\n\nPortofolio Anda terlalu berat di satu keranjang! **{sektor_terbesar['Persentase']:.1f}%** uang Anda tertumpuk di sektor **{sektor_terbesar['Sektor']}**. Jika sektor ini jatuh, seluruh uang Anda akan ikut amblas.")
                        st.info("💡 **Resep Dokter:** Disarankan untuk memindahkan sebagian (Re-balancing) dana dari sektor ini ke sektor lain seperti Consumer, Energi, atau Kripto agar portofolio Anda lebih tahan banting terhadap krisis.")
                    elif sektor_terbesar['Persentase'] >= 40:
                        st.warning(f"⚖️ **STATUS: PERLU PERHATIAN**\n\nSekitar **{sektor_terbesar['Persentase']:.1f}%** dana Anda ada di sektor **{sektor_terbesar['Sektor']}**. Ini masih wajar, tapi pertimbangkan untuk menambah aset di sektor lain agar diversifikasi lebih seimbang.")
                    else:
                        st.success(f"✅ **STATUS: SANGAT SEHAT**\n\nDiversifikasi Anda luar biasa! Tidak ada satu pun sektor yang memonopoli lebih dari 40% portofolio Anda. Teruskan strategi ini!")

    # ---------------------------------------------------------
    # TAB 2: CHATBOT AI GEMINI
    # ---------------------------------------------------------
    with tab_chat:
        st.markdown("### Ngobrol dengan AI Quant Advisor")
        st.caption("Ketik pertanyaan seputar saham, kripto, atau kondisi makro ekonomi saat ini.")
        
        # Form Input API Key (Hanya diminta sekali per sesi)
        if "gemini_api_key" not in st.session_state:
            st.session_state.gemini_api_key = ""
            
        if not st.session_state.gemini_api_key:
            st.info("🔐 Untuk mengaktifkan otak AI, Anda memerlukan API Key Google Gemini (Gratis).")
            with st.form("api_form"):
                kunci_api = st.text_input("Masukkan Google Gemini API Key Anda:", type="password")
                st.markdown("[Klik di sini untuk membuat API Key gratis di Google AI Studio](https://aistudio.google.com/app/apikey)")
                if st.form_submit_button("Aktifkan AI", width="stretch"):
                    if kunci_api:
                        st.session_state.gemini_api_key = kunci_api
                        st.success("Otak AI Berhasil Terhubung!"); st.rerun()
                    else:
                        st.error("API Key tidak boleh kosong.")
        
        # Jika API Key sudah dimasukkan, tampilkan antarmuka chat
        else:
            if st.button("Ubah API Key / Hapus Sesi", key="reset_api"):
                st.session_state.gemini_api_key = ""
                st.session_state.messages = []
                st.rerun()
                
            genai.configure(api_key=st.session_state.gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Inisialisasi memori chat
            if "messages" not in st.session_state:
                st.session_state.messages = [{"role": "assistant", "content": f"Halo {user_now.capitalize()}! Saya adalah Asisten Keuangan Pribadi Anda. Ada yang bisa saya bantu analisis hari ini?"}]

            # Tampilkan riwayat chat
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Input pesan dari user
            if prompt := st.chat_input("Contoh: Tolong analisis apakah bagus beli BBCA saat ini?"):
                # Tambahkan pesan user ke memori dan tampilkan di layar
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Persiapkan prompt sistem (menyuntikkan konteks agar AI menjawab layaknya ahli keuangan)
                system_prompt = "Anda adalah seorang penasihat keuangan profesional, ahli kuantitatif pasar modal (IDX), dan pakar kripto (Indodax). Jawablah pertanyaan user dengan bahasa Indonesia yang profesional, ringkas, berikan poin-poin tegas, dan hindari kata-kata yang terlalu berbunga-bunga. Pertanyaan User: " + prompt
                
                with st.chat_message("assistant"):
                    with st.spinner("AI sedang berpikir..."):
                        try:
                            # Tembak ke API Google Gemini
                            response = model.generate_content(system_prompt)
                            teks_balasan = response.text
                            st.markdown(teks_balasan)
                            # Simpan ke memori
                            st.session_state.messages.append({"role": "assistant", "content": teks_balasan})
                        except Exception as e:
                            st.error(f"Maaf, terjadi kesalahan koneksi ke otak AI. Pastikan API Key Anda valid. Error: {e}")
