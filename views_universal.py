# views_universal.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import time
from core import *

def render_kalkulator(zona_market):
    st.markdown(f"<h2 class='gradient-text'>Kalkulator Manajemen Risiko</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menyelamatkan Uang Anda:**
        * **Kalkulator Risiko:** Sebelum beli aset, masukkan modal dan batas rugi. Beli lot sesuai angka "BELI MAKSIMAL". Jangan serakah!
        * **Averaging Down:** Khusus kalau Anda sudah nyangkut parah. Kalkulator ini mencari titik impas baru (BEP) jika Anda membeli lagi di harga bawah.
        * **Kelly Criterion:** Rumus Anti-Bangkrut kasino. AI akan melihat rekam jejak jurnal Anda (Win Rate). Jika disarankan alokasi 10%, berarti jangan beli 1 aset pakai 100% uang Anda!
        """)
        
    tab_risk, tab_avg, tab_comp, tab_kelly = st.tabs(["🛡️ KALK. RISIKO", "🛟 AVERAGING DOWN", "📈 JALUR 1 MILIAR", "⚖️ KELLY CRITERION"])
    
    with tab_risk:
        st.info("Hitung lot/unit maksimal agar modal tidak habis saat terpaksa Cut Loss.")
        with st.form("risk_calc_form"):
            c1, c2 = st.columns(2)
            capital = c1.number_input("Modal Trading Disiapkan (Rp)", min_value=100.0, value=10000000.0, step=50000.0, format="%g")
            risk_pct = c2.number_input("Toleransi Rugi Maksimal (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1, format="%g")
            c3, c4 = st.columns(2)
            entry_p = c3.number_input("Rencana Harga Beli / Entry (Rp)", min_value=1.0, value=5000.0, step=100.0, format="%g")
            stop_loss_p = c4.number_input("Batas Harga Cut Loss (Rp)", min_value=1.0, value=4800.0, step=100.0, format="%g")
            calc_btn = st.form_submit_button("Kalkulasi Lot/Unit Aman", width="stretch")
            
        if calc_btn:
            if stop_loss_p >= entry_p: st.error("⚠️ Batas Harga Cut Loss harus lebih rendah dari Harga Beli!")
            else:
                max_risk_idr = capital * (risk_pct / 100)
                risk_per_share = entry_p - stop_loss_p
                total_lots = math.floor((max_risk_idr / risk_per_share) / 100) if zona_market == "🏢 ZONA SAHAM (IDX)" else (max_risk_idr / risk_per_share)
                actual_shares = total_lots * 100 if zona_market == "🏢 ZONA SAHAM (IDX)" else total_lots
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                if zona_market == "🏢 ZONA SAHAM (IDX)":
                    m1.metric("BELI MAKSIMAL", f"{total_lots:,.0f} Lot")
                    m2.metric("MODAL DIBUTUHKAN", f"Rp {actual_shares * entry_p:,.0f}")
                    m3.metric("UANG HILANG (JIKA CL)", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
                else:
                    m1.metric("BELI MAKSIMAL", f"{total_lots:,.4f} Unit")
                    m2.metric("MODAL DIBUTUHKAN", f"Rp {actual_shares * entry_p:,.0f}")
                    m3.metric("UANG HILANG (JIKA CL)", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
                
    with tab_avg:
        st.info("Penyelamat portofolio: Hitung lot/unit tambahan yang diperlukan untuk menurunkan beban harga rata-rata pada posisi yang menyangkut (Average Down).")
        with st.form("avg_calc_form"):
            c1, c2 = st.columns(2)
            p1 = c1.number_input("Harga Tersangkut (Atas)", min_value=1.0, value=1000.0, format="%g")
            l1 = c2.number_input("Jumlah Lot/Unit Nyangkut", min_value=0.0001, value=10.0, format="%g")
            c3, c4 = st.columns(2)
            p2 = c3.number_input("Harga Bawah Saat Ini", min_value=1.0, value=800.0, format="%g")
            l2 = c4.number_input("Rencana Pembelian Baru", min_value=0.0001, value=20.0, format="%g")
            calc_avg_btn = st.form_submit_button("Hitung Harga Penyelamatan", width="stretch")
            
        if calc_avg_btn:
            if p2 >= p1: st.error("⚠️ Harga pembelian tambahan harus lebih murah dari harga nyangkut!")
            else:
                pengali = 100 if zona_market == "🏢 ZONA SAHAM (IDX)" else 1
                total_modal_lama = p1 * l1 * pengali
                total_modal_baru = p2 * l2 * pengali
                total_lot_akhir = l1 + l2
                new_avg = (total_modal_lama + total_modal_baru) / (total_lot_akhir * pengali)
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                
                if zona_market == "🏢 ZONA SAHAM (IDX)":
                    a1.metric("HARGA BEP BARU", f"Rp {new_avg:,.0f}")
                    a2.metric("TOTAL KESELURUHAN LOT", f"{total_lot_akhir:,.0f} Lot")
                    a3.metric("DANA TAMBAHAN DIPERLUKAN", f"Rp {total_modal_baru:,.0f}")
                    st.success(f"Harga rata-ratamu berhasil turun ke level aman **Rp {new_avg:,.0f}**. Jual posisi segera ketika harga mencapai titik ini.")
                else:
                    a1.metric("HARGA BEP BARU", f"Rp {new_avg:,.0f}")
                    a2.metric("TOTAL KESELURUHAN UNIT", f"{total_lot_akhir:,.4f} Unit")
                    a3.metric("DANA TAMBAHAN DIPERLUKAN", f"Rp {total_modal_baru:,.0f}")
                    st.success(f"Harga rata-ratamu berhasil turun ke level aman **Rp {new_avg:,.0f}**.")
                
    with tab_comp:
        st.info("Kalkulator Bunga Berbunga (Compounding). Hitung secara presisi kapan portofoliomu akan menembus Rp 1 Miliar!")
        with st.form("comp_form"):
            c1, c2 = st.columns(2)
            p_awal = c1.number_input("Modal Awal Saat Ini (Rp)", min_value=100000.0, value=10000000.0, step=1000000.0, format="%g")
            r_bulan = c2.number_input("Target Profit Konsisten per Bulan (%)", min_value=0.1, max_value=100.0, value=5.0, step=0.5, format="%g")
            btn_comp = st.form_submit_button("Hitung Peta Jalan 1 Miliar", width="stretch")
        
        if btn_comp:
            target_fv = 1000000000
            if p_awal >= target_fv:
                st.success("🎉 Luar Biasa! Anda sudah memiliki lebih dari 1 Miliar di tangan Anda!")
            else:
                r_decimal = r_bulan / 100
                months_needed = math.log(target_fv / p_awal) / math.log(1 + r_decimal)
                years = int(months_needed // 12)
                months = int(math.ceil(months_needed % 12))
                
                if months == 12:
                    years += 1
                    months = 0
                
                st.markdown("---")
                st.markdown(f"<h3 style='text-align:center; color:#2563EB;'>Pencapaian 1 Miliar Anda:</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#10B981; font-size:3.5rem; margin-bottom:0;'>{years} Tahun {months} Bulan</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.info(f"💡 Dengan modal awal **Rp {p_awal:,.0f}** dan konsistensi profit **{r_bulan}% tiap bulan** tanpa ditarik, kekuatan bunga berbunga (*compounding interest*) akan melipatgandakan aset Anda menjadi Rp 1 Miliar dalam waktu **{years} tahun {months} bulan**. Tetap disiplin dan bersabar!")

    with tab_kelly:
        with st.form("kelly_form"):
            c1, c2 = st.columns(2)
            w_rate = c1.number_input("Win Rate Trading Anda (%) (Lihat Jurnal AI)", min_value=1.0, max_value=100.0, value=55.0, format="%g")
            rr_ratio = c2.number_input("Risk/Reward Ratio (Misal 2 untuk target cuan 2x lipat dari risiko cut loss)", min_value=0.1, max_value=10.0, value=2.0, format="%g")
            btn_kelly = st.form_submit_button("Hitung Batas Maksimal Pembelian", width="stretch")
            
        if btn_kelly:
            W = w_rate / 100
            R = rr_ratio
            kelly_pct = W - ((1 - W) / R)
            
            st.markdown("---")
            if kelly_pct <= 0:
                st.error("⚠️ **STOP TRADING SEMENTARA!** Sistem Anda saat ini merugikan secara matematis. Anda harus memperbaiki Win Rate atau memperbesar target keuntungan Anda (Risk/Reward) sebelum menaruh uang lagi ke market.")
            else:
                st.markdown(f"<h3 style='text-align:center; color:#2563EB;'>Alokasi Dana Maksimal (Per Transaksi):</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#10B981; font-size:3.5rem; margin-bottom:0;'>{kelly_pct*100:.1f}%</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"💡 Pemenang Nobel Matematika menyarankan Anda untuk TIDAK menggunakan lebih dari **{kelly_pct*100:.1f}% total modal Anda** untuk 1 posisi transaksi (berdasarkan statistik pribadi Anda). Ini adalah batas pertahanan agar portofolio Anda tidak akan pernah hancur (margin call).")


def render_dompet(user_now, role):
    st.markdown(f"<h2 class='gradient-text'>Dompet Omni-Wallet & AI Jurnal</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Sistem Akumulasi Kekayaan Pintar (Saham + Kripto 100% Rupiah):**
        * **Saham:** Ketik kodenya (`BBCA`), Beli & Live dalam **Rupiah**, Satuan **Lot**.
        * **Kripto Indodax:** Ketik kodenya (`CEL`, `BTC`, `PEPE`), Beli & Live otomatis 100% **Rupiah**, Satuan **Unit**.
        """)
        
    c_title, c_toggle = st.columns([3, 1])
    show_saldo = c_toggle.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 KEPEMILIKAN ASET", "📜 RIWAYAT", "📊 AUDIT AI JURNAL"])
    
    with tab1:
        with st.expander("➕ DAFTARKAN PEMBELIAN ASET BARU", expanded=False):
            tipe_aset_input = st.radio("PILIH JENIS ASET:", ["🏢 Saham Indonesia (IDX)", "🪙 Kripto (Indodax)"], horizontal=True)
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2 = st.columns(2)
                
                if "Saham" in tipe_aset_input:
                    t_in = c1.text_input("Kode Saham (Cth: BBCA)").upper().strip()
                    l_in = c2.number_input("Jumlah Lot (1 Lot = 100 Lembar)", min_value=1.0, value=1.0, step=1.0, format="%g")
                    p_in = st.number_input("Harga Beli (Rp per Lembar)", min_value=1.0, value=1000.0, step=50.0, format="%g")
                else:
                    t_in = c1.text_input("Kode Koin (Cth: BTC, PEPE)").upper().strip()
                    l_in = c2.number_input("Jumlah Koin (Unit)", min_value=0.000001, value=1.0, step=0.1, format="%g")
                    p_in = st.number_input("Harga Beli (Rp per Unit Koin)", min_value=1.0, value=1000.0, step=100.0, format="%g")
                    
                strat_in = st.selectbox("Faktor Justifikasi Beli?", ["Golden Cross MA", "Breakout Resistance", "Serok Bawah (Support)", "Ikut Berita", "Fundamental Bagus", "Feeling / FOMO"])
                
                if st.form_submit_button("MASUKKAN DALAM SISTEM", width="stretch"):
                    if t_in and p_in > 0: 
                        add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in)
                        st.success("Aset Berhasil Tersimpan di Cloud!"); time.sleep(1); st.rerun()

        df_p = get_user_portfolio(user_now, role)
        if not df_p.empty:
            indo_tickers = get_indodax_tickers()
            
            saham_tickers = [f"{t}.JK" for t in df_p['ticker'].unique() if not is_crypto_ticker(t)]
            live_prices_saham = {}
            if saham_tickers:
                try:
                    df_dl = yf.download(saham_tickers, period="5d", progress=False, threads=True)['Close']
                    for st_tk in saham_tickers:
                        try:
                            s = df_dl[st_tk].dropna() if isinstance(df_dl, pd.DataFrame) else df_dl.dropna()
                            if not s.empty: live_prices_saham[st_tk] = float(s.iloc[-1])
                        except: pass
                except: pass

            def calc_omni_active_idr(row):
                tk_asli = row['ticker'].strip().upper()
                clean_t = tk_asli.lower() + "_idr"
                is_crypto = is_crypto_ticker(tk_asli)
                
                bp_rp = float(row['buy_price'])
                lots = float(row['lots'])
                
                if is_crypto:
                    curr_price_rp = float(indo_tickers.get(clean_t, {}).get('last', 0))
                    
                    if curr_price_rp == 0:
                        try:
                            yf_usd = float(yf.Ticker(f"{tk_asli}-USD").fast_info.get('lastPrice', 0))
                            if yf_usd > 0: curr_price_rp = yf_usd * 15500
                            else: curr_price_rp = bp_rp
                        except: curr_price_rp = bp_rp
                        
                    cost_rp = bp_rp * lots
                    val_rp = curr_price_rp * lots
                else:
                    tk_yf = f"{tk_asli}.JK"
                    curr_price_rp = float(live_prices_saham.get(tk_yf, 0))
                    
                    if curr_price_rp == 0:
                        try:
                            p_info = yf.Ticker(tk_yf).fast_info.get('lastPrice', 0)
                            if p_info > 0: curr_price_rp = float(p_info)
                            else: curr_price_rp = bp_rp
                        except: curr_price_rp = bp_rp
                        
                    cost_rp = bp_rp * lots * 100
                    val_rp = curr_price_rp * lots * 100
                    
                pnl_rp = val_rp - cost_rp
                return pd.Series([curr_price_rp, cost_rp, val_rp, pnl_rp, is_crypto])

            df_p[['Live_Rp', 'Cost_IDR', 'Value_IDR', 'PnL_IDR', 'Is_Crypto']] = df_p.apply(calc_omni_active_idr, axis=1)
            t_inv_rp, t_pl_rp = df_p['Cost_IDR'].sum(), df_p['PnL_IDR'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("TOTAL MODAL (Rp)", format_privacy(t_inv_rp))
            m2.metric("TOTAL CUAN/RUGI (Rp)", format_privacy(t_pl_rp), f"{(t_pl_rp/t_inv_rp*100 if t_inv_rp!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("TOTAL KEKAYAAN (Rp)", format_privacy(t_inv_rp + t_pl_rp))

            st.markdown("---")
            for i, row in df_p.iterrows():
                strat_label = row.get('strategy', 'Bebas')
                is_cr = row['Is_Crypto']
                satuan = "Unit" if is_cr else "Lot"
                
                bp_val = float(row['buy_price'])
                live_val = float(row['Live_Rp'])
                pnl_val = float(row['PnL_IDR'])
                
                pct_val = (pnl_val / row['Cost_IDR'] * 100) if row['Cost_IDR'] > 0 else 0
                sign_str = "+" if pnl_val > 0 else ""
                
                fmt_qty = f"{row['lots']:.4f}" if is_cr else f"{row['lots']:.0f}"
                icon = "🪙" if is_cr else "🏢"
                title_text = f"{icon} {row['ticker']} | {fmt_qty} {satuan} | Beli: Rp {bp_val:,.0f} | Live: Rp {live_val:,.0f} | Profit: {sign_str}Rp {pnl_val:,.0f} ({sign_str}{pct_val:.2f}%)"

                with st.expander(title_text):
                    st.markdown(f"<span class='badge-blue'>Kategori: {strat_label}</span>", unsafe_allow_html=True)
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    
                    s_price = c_price.number_input("Harga Jual (Rp)", value=float(live_val), step=100.0, format="%g", key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input(f"Jumlah Dilepas?", min_value=0.000001, max_value=float(row['lots']), value=float(row['lots']), step=(0.01 if is_cr else 1.0), format="%g", key=f"s_lot_{row['id']}")
                    
                    if c_btn.button("LIKUIDASI", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Sistem perbendaharaan belum mencatatkan transaksi apapun.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                with st.expander(f"{h_row['date']} | {h_row['ticker']}"):
                    c_t, c_b = st.columns([4,1])
                    c_t.write(f"Dasar Strategi: **{h_row.get('strategy', 'Tidak Terekam')}**")
                    satuan_h = "Unit" if is_crypto_ticker(h_row['ticker']) else "Lot"
                    c_t.write(f"Avg Beli: Rp {h_row['buy_price']:,.0f} | Avg Jual: Rp {h_row['sell_price']:,.0f} | Pelepasan: {h_row['lots']} {satuan_h} | Profit: {format_privacy(h_row['pnl'])}")
                    if c_b.button("🗑️ Hapus Bukti", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            df_h_sorted = df_h.sort_values('date')
            df_h_sorted['Cumulative_PnL'] = df_h_sorted['pnl'].cumsum()
            
            fig_eq = px.area(df_h_sorted, x='date', y='Cumulative_PnL', title="📈 Kurva Pertumbuhan Ekuitas (Kinerja Trading Saham & Kripto)")
            fig_eq.update_traces(line_color='#2563EB', fillcolor='rgba(37, 99, 235, 0.2)')
            fig_eq.update_layout(template="plotly_white", height=300, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_eq, use_container_width=True)
            
            if 'strategy' in df_h.columns:
                strat_analysis = df_h.groupby('strategy').apply(
                    lambda x: pd.Series({'Total Trading': len(x), 'Win Rate (%)': (x['pnl'] > 0).mean() * 100})
                ).reset_index()
                
                if not strat_analysis.empty:
                    best_strat = strat_analysis.loc[strat_analysis['Win Rate (%)'].idxmax()]
                    st.success(f"💡 **Saran Sistem AI:** Statistik mencatat bahwa Anda paling handal ketika menggunakan justifikasi **'{best_strat['strategy']}'** dengan tingkat konfirmasi profit {best_strat['Win Rate (%)']:.0f}%. Disarankan untuk lebih disiplin menunggu sinyal dari metode ini.")
            
            total_trades = len(df_h)
            win_trades = len(df_h[df_h['pnl'] > 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric("KEMAMPUAN MENANG (WIN RATE)", f"{win_rate:.1f}%")
            c2.metric("REKAMAN FREKUENSI TRANSAKSI", f"{total_trades} Entri")

def render_user_management():
    st.markdown(f"<h2 class='gradient-text'>Portal Administratif</h2>", unsafe_allow_html=True)
    st.caption("Super-user dashboard untuk pengurusan identitas anggota sistem terminal.")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    with st.form("add_u"):
        nu, np, nr = st.text_input("Registrasi Node ID"), st.text_input("Sandikunci", type="password"), st.selectbox("Role Izin", ["user", "admin"])
        if st.form_submit_button("SETUJUI KREDENSIAL BARU", width="stretch"):
            if add_user_db(nu, np, nr): st.success("Basis Data Diperbarui!"); st.rerun()
    with st.form("del_u"):
        du = st.text_input("Masukan ID Node Terminal untuk dihapus")
        if st.form_submit_button("BLOKIR AKSES PERMANEN", width="stretch"):
            if delete_user_db(du): st.warning("Akses Terminal Berhasil Dihanguskan!"); st.rerun()

def render_keamanan(user_now):
    st.markdown(f"<h2 class='gradient-text'>Keamanan Node Terminal</h2>", unsafe_allow_html=True)
    st.caption("Pusat perlindungan enkripsi akses ke modul portofolio privat Anda.")
    with st.form("p"):
        new_p = st.text_input("Ketikan Sandikunci Baru", type="password")
        if st.form_submit_button("ENKRIPSI DAN SIMPAN", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Sandikunci berhasil diubah dan diamankan oleh sistem!")
