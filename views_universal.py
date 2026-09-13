# --- FILE: views_universal.py ---
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import time
import re
from core import *
import google.generativeai as genai

def render_kalkulator(zona_market):
    st.markdown(f"<h2 class='gradient-text'>🧮 Kalkulator Trading</h2>", unsafe_allow_html=True)
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
                if months == 12: years += 1; months = 0
                
                st.markdown("---")
                st.markdown(f"<h3 style='text-align:center; color:#38BDF8;'>Pencapaian 1 Miliar Anda:</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#34D399; font-size:3.5rem; margin-bottom:0;'>{years} Tahun {months} Bulan</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.info(f"💡 Dengan modal awal **Rp {p_awal:,.0f}** dan konsistensi profit **{r_bulan}% tiap bulan** tanpa ditarik, kekuatan bunga berbunga (*compounding interest*) akan melipatgandakan aset Anda menjadi Rp 1 Miliar dalam waktu **{years} tahun {months} bulan**. Tetap disiplin dan bersabar!")

    with tab_kelly:
        with st.form("kelly_form"):
            c1, c2 = st.columns(2)
            w_rate = c1.number_input("Win Rate Trading Anda (%)", min_value=1.0, max_value=100.0, value=55.0, format="%g")
            rr_ratio = c2.number_input("Risk/Reward Ratio (Misal 2 untuk target cuan 2x lipat dari risiko cut loss)", min_value=0.1, max_value=10.0, value=2.0, format="%g")
            btn_kelly = st.form_submit_button("Hitung Batas Maksimal Pembelian", width="stretch")
            
        if btn_kelly:
            W = w_rate / 100
            R = rr_ratio
            kelly_pct = W - ((1 - W) / R)
            st.markdown("---")
            if kelly_pct <= 0:
                st.error("⚠️ **STOP TRADING SEMENTARA!** Sistem Anda saat ini merugikan secara matematis. Anda harus memperbaiki Win Rate atau memperbesar target keuntungan Anda sebelum menaruh uang lagi ke market.")
            else:
                st.markdown(f"<h3 style='text-align:center; color:#38BDF8;'>Alokasi Dana Maksimal (Per Transaksi):</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#34D399; font-size:3.5rem; margin-bottom:0;'>{kelly_pct*100:.1f}%</h1>", unsafe_allow_html=True)
                st.success(f"💡 Pemenang Nobel Matematika menyarankan Anda untuk TIDAK menggunakan lebih dari **{kelly_pct*100:.1f}% total modal Anda** untuk 1 posisi transaksi. Ini adalah batas pertahanan agar portofolio Anda tidak akan pernah hancur.")

def format_rp(val):
    if pd.isna(val) or val == 0: return "Rp 0"
    if val < 10: return f"Rp {val:,.4f}"
    elif val < 1000: return f"Rp {val:,.2f}"
    else: return f"Rp {val:,.0f}"

def render_dompet(user_now, role):
    st.markdown(f"<h2 class='gradient-text'>💼 Dompet Omni-Wallet Pro</h2>", unsafe_allow_html=True)
    show_saldo = st.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 KEPEMILIKAN", "📜 RIWAYAT", "📊 AUDIT JURNAL"])
    
    with tab1:
        with st.expander("➕ TAMBAH ASET", expanded=False):
            tipe_aset = st.radio("PILIH JENIS ASET:", ["🏢 Saham Indonesia (IDX)", "🪙 Kripto (Indodax & Global)"], horizontal=True)
            with st.form("form_add", clear_on_submit=True):
                c1, c2 = st.columns(2)
                if "Saham" in tipe_aset:
                    t_in = c1.text_input("Kode Saham (Cth: BBCA)").upper().strip()
                    l_in = c2.number_input("Jumlah Lot", min_value=1.0, value=1.0, step=1.0, format="%g")
                    p_in = st.number_input("Harga Beli (Rp per Lembar)", min_value=1.0, value=100.0, format="%g")
                else:
                    t_in = c1.text_input("Kode Koin (Cth: BTC, FWOG)").upper().strip()
                    l_in = c2.number_input("Jumlah Koin (Unit)", min_value=0.000001, value=1.0, step=0.1, format="%g")
                    p_in = st.number_input("Harga Beli Total (Rp per Unit)", min_value=1.0, value=100.0, format="%g")
                
                st.markdown("<p style='font-size:12px; color:#38BDF8;'>*Opsional: Pasang Target Cuan & Rugi (Visual Tracker)</p>", unsafe_allow_html=True)
                col_tp, col_sl = st.columns(2)
                tp_in = col_tp.number_input("Target Jual (Take Profit) Rp", min_value=0.0, value=0.0, format="%g")
                sl_in = col_sl.number_input("Batas Rugi (Cut Loss) Rp", min_value=0.0, value=0.0, format="%g")
                    
                strat_in = st.selectbox("Alasan Beli?", ["Serok Bawah", "Breakout", "Fundamental", "Feeling / FOMO"])
                if st.form_submit_button("MASUKKAN", width="stretch") and t_in and p_in > 0:
                    add_to_portfolio(user_now, t_in, p_in, l_in, tp_in, sl_in, strat_in, is_crypto=("Kripto" in tipe_aset))
                    st.success("Tersimpan!"); time.sleep(1); st.rerun()

        df_p = get_user_portfolio(user_now)
        if not df_p.empty:
            import requests
            try: indo = requests.get("https://indodax.com/api/tickers", timeout=5).json().get('tickers', {})
            except: indo = {}
            try: kurs_idr = float(yf.download("IDR=X", period="1d", progress=False)['Close'].iloc[-1])
            except: kurs_idr = 15500.0 
            
            df_p['Is_Cr_Strict'] = df_p['ticker'].apply(lambda x: is_crypto_ticker(str(x)))
            
            saham_tkrs = []
            for t in df_p[~df_p['Is_Cr_Strict']]['ticker'].unique():
                clean_t = str(t).strip().upper()
                if not clean_t.endswith(".JK"): clean_t += ".JK"
                saham_tkrs.append(clean_t)
                
            live_saham = {}
            if saham_tkrs:
                try:
                    df_dl = yf.download(list(set(saham_tkrs)), period="5d", progress=False, threads=True)['Close']
                    for tk in set(saham_tkrs): 
                        live_saham[tk] = float(df_dl[tk].dropna().iloc[-1]) if isinstance(df_dl, pd.DataFrame) else float(df_dl.dropna().iloc[-1])
                except: pass

            def calc_active(r):
                t = str(r['ticker']).strip().upper()
                is_cr = r['Is_Cr_Strict'] 
                
                bp, lots = float(r['buy_price']), float(r['lots'])
                
                if is_cr:
                    clean_t = t.replace('-USD','').replace('-IDR', '').lower() + "_idr"
                    curr_rp = float(indo.get(clean_t, {}).get('last', 0))
                    if curr_rp == 0:
                        try: 
                            usd_p = float(yf.Ticker(f"{t.replace('-USD','').replace('-IDR', '')}-USD").fast_info.get('lastPrice', 0))
                            curr_rp = usd_p * kurs_idr if usd_p > 0 else bp
                        except: curr_rp = bp
                    cost_rp, val_rp = bp * lots, curr_rp * lots
                    fee_cost = (cost_rp * 0.0021) + (val_rp * 0.0021) 
                else:
                    tk_yf = f"{t}.JK" if not t.endswith(".JK") else t
                    curr_rp = live_saham.get(tk_yf, 0)
                    if curr_rp == 0:
                        try: curr_rp = float(yf.Ticker(tk_yf).fast_info.get('lastPrice', bp))
                        except: curr_rp = bp
                    cost_rp, val_rp = bp * lots * 100, curr_rp * lots * 100
                    fee_cost = (cost_rp * 0.0015) + (val_rp * 0.0025)
                
                net_pnl = (val_rp - cost_rp) - fee_cost
                return pd.Series([curr_rp, cost_rp, val_rp, net_pnl, is_cr])

            df_p[['Live_Rp', 'Cost', 'Val', 'Net_PnL', 'Is_Cr']] = df_p.apply(calc_active, axis=1)
            
            st.write("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("MODAL MENGAMBANG", format_privacy(df_p['Cost'].sum()))
            m2.metric("NET PROFIT (Dipotong Fee)", format_privacy(df_p['Net_PnL'].sum()), f"{(df_p['Net_PnL'].sum()/df_p['Cost'].sum()*100 if df_p['Cost'].sum()!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("NILAI SEKARANG", format_privacy(df_p['Cost'].sum() + df_p['Net_PnL'].sum()))
            
            st.write("---")
            for _, r in df_p.iterrows():
                is_c, icon, sat = r['Is_Cr'], "🪙" if r['Is_Cr'] else "🏢", "Unit" if r['Is_Cr'] else "Lot"
                pct = (r['Net_PnL'] / r['Cost'] * 100) if r['Cost'] > 0 else 0
                sign = "+" if r['Net_PnL'] > 0 else ""
                
                title = f"{icon} {r['ticker']} | {r['lots']:g} {sat} | Live: {format_rp(r['Live_Rp'])} | Net PnL: {sign}Rp {r['Net_PnL']:,.0f} ({sign}{pct:.2f}%)"
                with st.expander(title):
                    st.markdown(f"<span class='badge-blue'>Kategori: {r.get('strategy', 'Bebas')}</span>", unsafe_allow_html=True)
                    
                    tp_val = float(r.get('tp_price', 0) if pd.notna(r.get('tp_price')) else 0)
                    sl_val = float(r.get('cl_price', 0) if pd.notna(r.get('cl_price')) else 0)
                    bp_val = float(r['buy_price'])
                    lv_val = float(r['Live_Rp'])
                    
                    if tp_val > 0 and sl_val > 0 and tp_val > sl_val:
                        jarak_total = tp_val - sl_val
                        posisi_skrng = ((lv_val - sl_val) / jarak_total) * 100
                        posisi_clamp = max(0, min(100, posisi_skrng)) 
                        bar_color = "#34D399" if posisi_skrng > 50 else "#EF4444"
                        st.markdown(f"""
                            <div style="margin: 15px 0;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; color: #94A3B8; margin-bottom: 4px;">
                                    <span>Cut Loss<br><b>Rp {sl_val:,.0f}</b></span>
                                    <span style="text-align:center;">Avg Beli<br><b>Rp {bp_val:,.0f}</b></span>
                                    <span style="text-align:right;">Take Profit<br><b>Rp {tp_val:,.0f}</b></span>
                                </div>
                                <div style="height: 10px; width: 100%; background: rgba(255,255,255,0.1); border-radius: 5px; position: relative;">
                                    <div style="position: absolute; top: 0; left: 0; width: {posisi_clamp}%; height: 10px; background: {bar_color}; border-radius: 5px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_prc = c_price.number_input("Harga Jual (Rp)", value=float(lv_val), format="%g", key=f"p_{r['id']}")
                    s_lot = c_lots.number_input(f"Jumlah Dilepas", min_value=0.000001, max_value=float(r['lots']), value=float(r['lots']), format="%g", key=f"l_{r['id']}")
                    if c_btn.button("JUAL", key=f"b_{r['id']}", use_container_width=True):
                        sell_position(user_now, r['id'], r['ticker'], r['buy_price'], s_prc, r['lots'], s_lot, is_crypto=is_c)
                        st.toast("Terjual!"); time.sleep(1); st.rerun()
        else: st.info("Dompet kosong.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            for _, r in df_h[df_h['username'] == user_now].sort_values('date', ascending=False).iterrows():
                display_tick_h = r['ticker'].replace("-IDR", "")
                with st.expander(f"{r['date']} | {display_tick_h} | Net Profit Nyata: {format_privacy(float(r['pnl']))}"):
                    if st.button("Hapus Rekor", key=f"d_{r['id']}"):
                        df_a = conn_gs.read(worksheet="history", ttl=0)
                        conn_gs.update(worksheet="history", data=df_a.drop(df_a.index[df_a['id'] == r['id']][0]).reset_index(drop=True)); st.rerun()

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            dh = df_h[df_h['username'] == user_now].sort_values('date').copy()
            if not dh.empty:
                dh['c'] = pd.to_numeric(dh['pnl']).cumsum()
                st.plotly_chart(px.area(dh, x='date', y='c', title="Kurva Profit Nyata (Sudah Dijual)").update_layout(template="plotly_dark", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True)

def render_dokter_portofolio(user_now, role):
    st.markdown("<h2 class='gradient-text'>🩺 Dokter Portofolio</h2>", unsafe_allow_html=True)
    st.caption("Sistem akan memindai dompet Anda untuk mendeteksi risiko konsentrasi yang berbahaya.")
    
    if st.button("Mulai Audit Kesehatan Keuangan", use_container_width=True):
        with st.spinner("Memindai sektor aset di dompet Anda..."):
            df_p = get_user_portfolio(user_now)
            
            if df_p.empty:
                st.warning("Dompet Anda masih kosong. Silakan beli beberapa aset di menu Dompet Trading terlebih dahulu.")
            else:
                def hitung_modal_idr(row):
                    tk_asli = str(row['ticker']).strip().upper()
                    is_cr = is_crypto_ticker(tk_asli)
                    pengali = 1 if is_cr else 100
                    return float(row['buy_price']) * float(row['lots']) * pengali
                
                df_p['Modal_IDR'] = df_p.apply(hitung_modal_idr, axis=1)
                df_p['Sektor'] = df_p['ticker'].apply(get_sector)
                
                distribusi = df_p.groupby('Sektor')['Modal_IDR'].sum().reset_index()
                total_semua_modal = distribusi['Modal_IDR'].sum()
                distribusi['Persentase'] = (distribusi['Modal_IDR'] / total_semua_modal) * 100
                
                fig_pie = px.pie(distribusi, values='Modal_IDR', names='Sektor', title='Distribusi Sektor Portofolio Anda',
                                 color_discrete_sequence=px.colors.sequential.Teal)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie, use_container_width=True)
                
                sektor_terbesar = distribusi.loc[distribusi['Persentase'].idxmax()]
                
                st.markdown("---")
                if sektor_terbesar['Persentase'] >= 70:
                    st.error(f"⚠️ **STATUS: BAHAYA (RISIKO TINGGI)**\n\nPortofolio Anda terlalu berat di satu keranjang! **{sektor_terbesar['Persentase']:.1f}%** uang Anda tertumpuk di sektor **{sektor_terbesar['Sektor']}**. Jika sektor ini jatuh, seluruh uang Anda akan ikut amblas.")
                    st.info("💡 **Resep Dokter:** Disarankan untuk memindahkan sebagian (Re-balancing) dana dari sektor ini ke sektor lain seperti Consumer, Energi, atau Kripto agar portofolio Anda lebih tahan banting terhadap krisis.")
                elif sektor_terbesar['Persentase'] >= 40:
                    st.warning(f"⚖️ **STATUS: PERLU PERHATIAN**\n\nSekitar **{sektor_terbesar['Persentase']:.1f}%** dana Anda ada di sektor **{sektor_terbesar['Sektor']}**. Ini masih wajar, tapi pertimbangkan untuk menambah aset di sektor lain agar diversifikasi lebih seimbang.")
                else:
                    st.success(f"✅ **STATUS: SANGAT SEHAT**\n\nDiversifikasi Anda luar biasa! Tidak ada satu pun sektor yang memonopoli lebih dari 40% portofolio Anda. Teruskan strategi ini!")


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

def render_ai_chat_panel(user_now, role):
    st.markdown("""
    <div style='background: linear-gradient(90deg, #38BDF8, #34D399); padding: 15px 20px; border-radius: 10px 10px 0 0; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
        <b style='font-size: 1.25rem; color: #0F172A;'>🤖 AI Quant Advisor</b>
    </div>
    """, unsafe_allow_html=True)
    
    nama_tampil = user_now.capitalize() if user_now else "Trader"
    c1, c2 = st.columns(2)
    if c1.button("🗑️ Bersihkan Chat", use_container_width=True, key="clear_chat_btn"):
        st.session_state.messages = [{"role": "assistant", "content": f"Halo {nama_tampil}! Saya AI Advisor siap membantu analisis pasar Anda."}]
        st.rerun()
        
    if c2.button("✖️ Tutup Panel AI", use_container_width=True, key="close_panel_btn"):
        st.session_state.show_ai_panel = False
        st.rerun()

    api_key_rahasia = None
    if "GEMINI_API_KEY" in st.secrets:
        api_key_rahasia = st.secrets["GEMINI_API_KEY"]
        
    if not api_key_rahasia:
        st.error("⚠️ Kunci API (API Key) belum dikonfigurasi. Silakan tambahkan 'GEMINI_API_KEY' di pengaturan rahasia (Secrets) Streamlit.")
        return
        
    genai.configure(api_key=api_key_rahasia)
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": f"Halo {nama_tampil}! Saya AI Advisor siap membantu analisis pasar Anda."}]

    chat_container = st.container(height=500, border=True)
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Tanya AI (Cth: Analisis fundamental ASII)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Mengambil data live pasar..."):
                    
                    # --- FITUR BARU: INJEKSI DATA LIVE KE OTAK AI (RAG V2) ---
                    live_context = ""
                    # Ambil semua kata berukuran 3-5 huruf dari prompt user (contoh: BBCA, BUMI, BTC)
                    potential_tickers = [w.upper() for w in re.findall(r'\b[a-zA-Z]{3,5}\b', prompt)]
                    
                    if potential_tickers:
                        live_context += "INFO WAJIB UNTUK AI (GUNAKAN HARGA INI SEBAGAI PATOKAN ANALISIS, JANGAN MENGARANG):\n"
                        # Hapus kata duplikat agar prosesnya lebih ringan
                        seen = set()
                        unique_tickers = [x for x in potential_tickers if not (x in seen or seen.add(x))]
                        
                        valid_count = 0
                        for tk in unique_tickers:
                            if valid_count >= 3: break # Maksimal narik 3 aset agar loading tidak lemot
                            
                            is_crypto_check = is_crypto_ticker(tk)
                            try:
                                if is_crypto_check:
                                    # Pake fast_info yang 10x lebih ngebut dari .download
                                    price = float(yf.Ticker(f"{tk}-USD").fast_info['lastPrice'])
                                    live_context += f"- HARGA LIVE KRIPTO {tk} SAAT INI: $ {price:,.4f}\n"
                                    valid_count += 1
                                    continue
                            except: pass
                            
                            try:
                                # Jika bukan kripto, coba tembak sebagai Saham IDX
                                price = float(yf.Ticker(f"{tk}.JK").fast_info['lastPrice'])
                                live_context += f"- HARGA LIVE SAHAM {tk} SAAT INI: Rp {price:,.0f}\n"
                                valid_count += 1
                            except: pass

                    system_prompt = f"Anda adalah penasihat keuangan kuantitatif profesional untuk pasar saham IDX dan aset Kripto. Anda berbicara dengan {nama_tampil}. {live_context}\nJawablah secara ringkas, analitis, langsung pada intinya (to the point), dan gunakan bahasa Indonesia yang formal namun mudah dipahami. Hindari bahasa yang terlalu berbunga-bunga. Pertanyaan User: {prompt}"
                    
                    sukses, log_error = False, ""
                    try:
                        daftar_model = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        daftar_model.sort(key=lambda x: (not ('flash' in x.lower()), not ('pro' in x.lower()), x))
                        for nama_model in daftar_model:
                            try:
                                model = genai.GenerativeModel(nama_model)
                                response = model.generate_content(system_prompt)
                                if response:
                                    try: teks_balasan = response.text
                                    except ValueError: teks_balasan = "Mohon maaf, sistem keamanan memblokir respons ini karena mengandung kata kunci yang dibatasi."
                                    st.markdown(teks_balasan)
                                    st.session_state.messages.append({"role": "assistant", "content": teks_balasan})
                                    sukses = True
                                    break 
                            except Exception as e:
                                log_error += f"[{nama_model} gagal] "
                                continue 
                        if not sukses:
                            st.error(f"⚠️ Saat ini server AI sedang sibuk atau menolak koneksi. Log teknis: {log_error}")
                    except Exception as e:
                        st.error(f"Kesalahan sistem internal: {e}")
        st.rerun() 
