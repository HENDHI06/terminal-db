# --- FILE: views_universal.py ---
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import time
import re
import requests
import feedparser
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

def topup_asset(row_id, new_p, new_l, is_cr):
    df_port = conn_gs.read(worksheet="portfolio", ttl=0)
    idx = df_port.index[df_port['id'] == row_id].tolist()
    if idx:
        old_p = float(df_port.at[idx[0], 'buy_price'])
        old_l = float(df_port.at[idx[0], 'lots'])
        pengali = 1 if is_cr else 100
        total_modal_lama = old_p * old_l * pengali
        total_modal_baru = new_p * new_l * pengali
        total_lot_baru = old_l + new_l
        avg_p = (total_modal_lama + total_modal_baru) / (total_lot_baru * pengali)
        df_port.at[idx[0], 'buy_price'] = avg_p
        df_port.at[idx[0], 'lots'] = total_lot_baru
        conn_gs.update(worksheet="portfolio", data=df_port)
        return True
    return False

def render_dompet(user_now, role):
    st.markdown(f"<h2 class='gradient-text'>💼 Dompet Omni-Wallet Pro</h2>", unsafe_allow_html=True)
    show_saldo = st.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab_passive, tab3 = st.tabs(["📈 KEPEMILIKAN", "📜 RIWAYAT (REALIZED)", "💰 PASIF INCOME", "📊 AUDIT JURNAL AI"])
    
    df_h_all = conn_gs.read(worksheet="history", ttl=0)
    total_passive_income = 0
    if not df_h_all.empty:
        df_h_user = df_h_all[df_h_all['username'] == user_now].copy()
        df_h_user['pnl'] = pd.to_numeric(df_h_user['pnl'], errors='coerce')
        total_passive_income = df_h_user[df_h_user['strategy'] == 'PASIF_INCOME']['pnl'].sum()
        
    with tab1:
        with st.expander("➕ BELI ASET BARU", expanded=False):
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
                
                st.markdown("<p style='font-size:12px; color:#38BDF8;'>*Opsional: Pasang Target agar dipantau AI</p>", unsafe_allow_html=True)
                col_tp, col_sl = st.columns(2)
                tp_in = col_tp.number_input("Target Jual (Take Profit) Rp", min_value=0.0, value=0.0, format="%g")
                sl_in = col_sl.number_input("Batas Rugi (Cut Loss) Rp", min_value=0.0, value=0.0, format="%g")
                    
                strat_in = st.selectbox("Alasan Beli (Untuk dievaluasi AI nantinya):", ["Serok Bawah", "Breakout", "Fundamental", "Feeling / FOMO"])
                if st.form_submit_button("MASUKKAN KE DOMPET", width="stretch") and t_in and p_in > 0:
                    add_to_portfolio(user_now, t_in, p_in, l_in, tp_in, sl_in, strat_in, is_crypto=("Kripto" in tipe_aset))
                    st.success("Tersimpan di Cloud!"); time.sleep(1); st.rerun()

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
            
            t_inv_rp, t_pl_rp = df_p['Cost'].sum(), df_p['Net_PnL'].sum()
            total_kekayaan = t_inv_rp + t_pl_rp + total_passive_income
            
            m1, m2, m3 = st.columns(3)
            m1.metric("MODAL MENGAMBANG", format_privacy(t_inv_rp))
            m2.metric("NET PROFIT (Dipotong Fee)", format_privacy(t_pl_rp), f"{(t_pl_rp/t_inv_rp*100 if t_inv_rp!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("TOTAL KEKAYAAN AKTIF", format_privacy(total_kekayaan), f"+ Rp {total_passive_income:,.0f} Pasif Income" if show_saldo and total_passive_income > 0 else "")
            
            st.write("---")
            for _, r in df_p.iterrows():
                is_c, icon, sat = r['Is_Cr'], "🪙" if r['Is_Cr'] else "🏢", "Unit" if r['Is_Cr'] else "Lot"
                pct = (r['Net_PnL'] / r['Cost'] * 100) if r['Cost'] > 0 else 0
                sign = "+" if r['Net_PnL'] > 0 else ""
                
                title = f"{icon} {r['ticker']} | {r['lots']:g} {sat} | Live: {format_rp(r['Live_Rp'])} | Net PnL: {sign}Rp {r['Net_PnL']:,.0f} ({sign}{pct:.2f}%)"
                
                with st.expander(title):
                    st.markdown(f"<span class='badge-blue'>{r.get('strategy', 'Bebas')}</span>", unsafe_allow_html=True)
                    
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
                                    <span style="text-align:right;">Target Profit<br><b>Rp {tp_val:,.0f}</b></span>
                                </div>
                                <div style="height: 10px; width: 100%; background: rgba(255,255,255,0.1); border-radius: 5px; position: relative;">
                                    <div style="position: absolute; top: 0; left: 0; width: {posisi_clamp}%; height: 10px; background: {bar_color}; border-radius: 5px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    tab_jual, tab_beli = st.tabs(["🔴 LIKUIDASI ASET", "🟢 BELI LAGI (AVERAGE DOWN/UP)"])
                    
                    with tab_jual:
                        cp, cl, cb = st.columns([2, 2, 1])
                        s_prc = cp.number_input("Harga Jual (Rp)", value=float(lv_val), format="%g", key=f"pj_{r['id']}")
                        s_lot = cl.number_input("Jumlah Dilepas", min_value=0.000001, max_value=float(r['lots']), value=float(r['lots']), format="%g", key=f"lj_{r['id']}")
                        if cb.button("JUAL", key=f"bj_{r['id']}", use_container_width=True):
                            sell_position(user_now, r['id'], r['ticker'], bp_val, s_prc, r['lots'], s_lot, is_crypto=is_c)
                            st.toast("Terjual!"); time.sleep(1); st.rerun()
                            
                    with tab_beli:
                        cp2, cl2, cb2 = st.columns([2, 2, 1])
                        b_prc = cp2.number_input("Harga Beli Baru (Rp)", value=float(lv_val), format="%g", key=f"pb_{r['id']}")
                        b_lot = cl2.number_input("Beli Tambahan?", min_value=0.000001, value=1.0 if not is_c else 0.1, format="%g", key=f"lb_{r['id']}")
                        if cb2.button("TOP UP", key=f"bb_{r['id']}", use_container_width=True):
                            if topup_asset(r['id'], b_prc, b_lot, is_c):
                                st.toast("Lot Berhasil Digabung!"); time.sleep(1); st.rerun()
        else: st.info("Dompet kosong.")

    with tab2:
        if not df_h_all.empty:
            df_h_trade = df_h_user[df_h_user['strategy'] != 'PASIF_INCOME']
            for _, r in df_h_trade.sort_values('date', ascending=False).iterrows():
                display_tick_h = r['ticker'].replace("-IDR", "")
                with st.expander(f"{r['date']} | {display_tick_h} | Profit: {format_privacy(float(r['pnl']))}"):
                    st.write(f"Harga Beli: Rp {r['buy_price']:,.0f} | Harga Jual: Rp {r['sell_price']:,.0f} | Alasan Beli: {r.get('strategy', 'Bebas')}")
                    if st.button("Hapus Rekor", key=f"d_{r['id']}"):
                        conn_gs.update(worksheet="history", data=df_h_all.drop(df_h_all.index[df_h_all['id'] == r['id']][0]).reset_index(drop=True)); st.rerun()

    with tab_passive:
        st.info("Pencatat Keuangan Khusus Dividen Saham & Hasil Staking Kripto. Uang ini dihitung sebagai Profit Murni (Modal = 0).")
        with st.form("form_passive_inc"):
            c_p1, c_p2 = st.columns([2, 1])
            sumber_dana = c_p1.text_input("Sumber Dana (Contoh: Dividen ITMG / Staking ETH)").upper().strip()
            jumlah_dana = c_p2.number_input("Total Uang Masuk (Rp)", min_value=1.0, value=500000.0, format="%g")
            if st.form_submit_button("Catat Pemasukan", width="stretch") and sumber_dana:
                df_hist_p = conn_gs.read(worksheet="history", ttl=0)
                n_id_p = int(pd.to_numeric(df_hist_p['id'], errors='coerce').max() + 1) if not df_hist_p.empty and 'id' in df_hist_p.columns else 1
                new_pasif = pd.DataFrame([{'id': n_id_p, 'username': user_now, 'ticker': sumber_dana, 'buy_price': 0, 'sell_price': 0, 'lots': 0, 'pnl': float(jumlah_dana), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': 'PASIF_INCOME'}])
                conn_gs.update(worksheet="history", data=pd.concat([df_hist_p, new_pasif], ignore_index=True))
                st.success("Pasif Income Berhasil Ditambahkan!"); time.sleep(1); st.rerun()
                
        df_pasif = df_h_user[df_h_user['strategy'] == 'PASIF_INCOME']
        if not df_pasif.empty:
            st.write("---")
            st.markdown(f"### Total Pemasukan Pasif: {format_privacy(total_passive_income)}")
            for _, r in df_pasif.sort_values('date', ascending=False).iterrows():
                st.markdown(f"💸 **{r['date']}** | {r['ticker']} | **+Rp {float(r['pnl']):,.0f}**")

    with tab3: 
        if not df_h_all.empty:
            df_h_trade = df_h_user[df_h_user['strategy'] != 'PASIF_INCOME'].copy()
            if not df_h_trade.empty:
                df_h_trade = df_h_trade.sort_values('date')
                df_h_trade['Cumulative_PnL'] = pd.to_numeric(df_h_trade['pnl']).cumsum()
                st.plotly_chart(px.area(df_h_trade, x='date', y='Cumulative_PnL', title="Kurva Profit Trading (Realized)").update_layout(template="plotly_dark", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
                
                st.markdown("### 🤖 Evaluasi Psikologi Trading (Rapor AI)")
                strat_analysis = df_h_trade.groupby('strategy').apply(
                    lambda x: pd.Series({'Total Transaksi': len(x), 'Win Rate (%)': (x['pnl'] > 0).mean() * 100, 'Total PnL': x['pnl'].sum()})
                ).reset_index()
                
                st.dataframe(strat_analysis.style.format({'Win Rate (%)': "{:.1f}%", 'Total PnL': "Rp {:,.0f}"}), hide_index=True, use_container_width=True)
                
                if len(strat_analysis) >= 2:
                    best_strat = strat_analysis.loc[strat_analysis['Win Rate (%)'].idxmax()]
                    worst_strat = strat_analysis.loc[strat_analysis['Win Rate (%)'].idxmin()]
                    
                    st.success(f"💡 **AI Menganalisis:** Berdasarkan rekam jejak, Anda sangat mahir menggunakan strategi **'{best_strat['strategy']}'** dengan tingkat kemenangan {best_strat['Win Rate (%)']:.0f}%. AI menyarankan Anda untuk terus berpegang pada metode ini.")
                    if worst_strat['Win Rate (%)'] < 50:
                        st.error(f"⚠️ **Peringatan AI:** Hentikan membeli aset dengan alasan **'{worst_strat['strategy']}'**. Data membuktikan strategi ini membuat Anda merugi dengan tingkat kemenangan hanya {worst_strat['Win Rate (%)']:.0f}%. Jangan diulangi!")

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
                    is_cr = getattr(row, 'is_crypto', False)
                    try:
                        if not is_cr: is_cr = is_crypto_ticker(tk_asli)
                    except: pass
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

# =======================================================
# 🧠 AI QUANT ADVISOR (GOD-TIER V6 - OMNI-AWARENESS)
# =======================================================
def render_ai_chat_panel(user_now, role):
    st.markdown("""
    <div style='background: linear-gradient(90deg, #38BDF8, #34D399); padding: 15px 20px; border-radius: 10px 10px 0 0; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
        <b style='font-size: 1.25rem; color: #0F172A;'>🤖 AI Quant Advisor (V6 God-Tier)</b>
    </div>
    """, unsafe_allow_html=True)
    
    nama_tampil = user_now.capitalize() if user_now else "Trader"
    c1, c2 = st.columns(2)
    if c1.button("🗑️ Bersihkan Chat", use_container_width=True, key="clear_chat_btn"):
        st.session_state.messages = [{"role": "assistant", "content": f"Halo {nama_tampil}! Mesin V6 siap menganalisis portofolio, memindai berita terkini, atau mencarikan saham diskon untuk Anda. Ada yang bisa saya bantu hari ini?"}]
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
        st.session_state.messages = [{"role": "assistant", "content": f"Halo {nama_tampil}! Mesin V6 siap menganalisis portofolio, memindai berita terkini, atau mencarikan saham diskon untuk Anda. Ada yang bisa saya bantu hari ini?"}]

    chat_container = st.container(height=500, border=True)
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Tanya AI (Cth: Evaluasi portofolio saya / Berita BBRI / Carikan saham diskon)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("🤖 Mengaktifkan Indra AI (Koneksi ke Market, Berita, & Dompet)..."):
                    
                    # 1. KONDISI MAKRO
                    macro_context = ""
                    try:
                        ihsg_price = float(yf.Ticker("^JKSE").fast_info['lastPrice'])
                        btc_price = float(yf.Ticker("BTC-USD").fast_info['lastPrice'])
                        macro_context += f"- Posisi IHSG Saat Ini: {ihsg_price:,.0f}\n"
                        macro_context += f"- Posisi Bitcoin (BTC) Saat Ini: $ {btc_price:,.0f}\n"
                    except: pass
                    
                    # 2. FITUR 1: MATA BATIN PORTOFOLIO (Membaca Dompet User)
                    portfolio_context = ""
                    if any(word in prompt.lower() for word in ['portofolio', 'dompet', 'aset', 'punya saya', 'cut loss', 'evaluasi', 'nyangkut', 'jual', 'beli']):
                        df_port = get_user_portfolio(user_now)
                        if not df_port.empty:
                            portfolio_context += "INFO RAHASIA: DATA PORTOFOLIO KLIEN SAAT INI (GUNAKAN INI JIKA KLIEN MEMINTA EVALUASI/SARAN CUTLOSS):\n"
                            for _, row in df_port.iterrows():
                                tk = str(row['ticker']).upper()
                                bp = float(row['buy_price'])
                                lots = float(row['lots'])
                                is_cr = is_crypto_ticker(tk)
                                sat = "Unit" if is_cr else "Lot"
                                try:
                                    if is_cr: lp = float(yf.Ticker(f"{tk.replace('-USD', '')}-USD").fast_info['lastPrice'])
                                    else: lp = float(yf.Ticker(f"{tk}.JK" if not tk.endswith(".JK") else tk).fast_info['lastPrice'])
                                    pct = ((lp - bp)/bp)*100
                                    portfolio_context += f"- Klien pegang {tk}: Beli @ Rp/USD {bp:,.0f}, Harga Skrg @ {lp:,.0f} (Floating Profit/Loss: {pct:+.2f}%)\n"
                                except: pass
                            portfolio_context += "\n"
                        else:
                            portfolio_context += "INFO: Klien saat ini TIDAK memiliki aset apa pun di dompetnya. Arahkan untuk mencari aset bagus.\n\n"

                    # 3. FITUR 3: AUTO-SCREENER SAHAM (Menyapu Saham Diskon)
                    screener_context = ""
                    if any(word in prompt.lower() for word in ['carikan', 'rekomendasi', 'screener', 'saham bagus', 'potensi', 'diskon', 'oversold']):
                        blue_chips = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "GOTO.JK", "ADRO.JK", "PGAS.JK", "ITMG.JK"]
                        screener_context += "INFO RAHASIA: HASIL RADAR SCREENING SAHAM BLUE CHIP SAAT INI:\n"
                        try:
                            df_blue = yf.download(blue_chips, period="1mo", progress=False)
                            if isinstance(df_blue.columns, pd.MultiIndex): df_close = df_blue['Close']
                            else: df_close = df_blue
                                
                            for bc in blue_chips:
                                try:
                                    c_data = df_close[bc].dropna()
                                    if len(c_data) > 15:
                                        c_p = float(c_data.iloc[-1])
                                        ma20 = float(c_data.tail(20).mean())
                                        
                                        # Fast RSI
                                        delta = c_data.diff()
                                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                                        rs = gain / loss
                                        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
                                        if math.isnan(rsi): rsi = 50.0
                                        
                                        trend = "Uptrend" if c_p > ma20 else "Downtrend"
                                        status_rsi = "Sangat Diskon (Oversold)" if rsi < 35 else "Kemahalan (Overbought)" if rsi > 70 else "Netral"
                                        screener_context += f"- {bc.replace('.JK','')}: Rp {c_p:,.0f} | Tren: {trend} | RSI: {rsi:.1f} ({status_rsi})\n"
                                except: pass
                            screener_context += "Berikan klien maksimal 3 saham terbaik (yang trennya naik atau lagi diskon besar) dari data di atas.\n\n"
                        except: pass

                    # 4. FITUR 2: ANALISIS TICKER SPESIFIK & PENCARI BERITA (SENTIMEN)
                    live_context = ""
                    potential_tickers = [w.upper() for w in re.findall(r'\b[a-zA-Z]{3,6}\b', prompt)]
                    if potential_tickers:
                        live_context += "INFO WAJIB UNTUK AI (DATA TEKNIKAL & SENTIMEN BERITA REAL-TIME):\n"
                        seen = set()
                        unique_tickers = [x for x in potential_tickers if not (x in seen or seen.add(x))]
                        
                        valid_count = 0
                        for tk in unique_tickers:
                            if valid_count >= 2: break 
                            
                            is_crypto_check = is_crypto_ticker(tk)
                            ticker_symbol = f"{tk}-USD" if is_crypto_check else f"{tk}.JK"
                            tipe_aset = "KRIPTO" if is_crypto_check else "SAHAM"
                            mata_uang = "$" if is_crypto_check else "Rp"
                            
                            try:
                                # A. Tarik Teknikal & Fundamental
                                df_raw = yf.download(ticker_symbol, period="2mo", progress=False)
                                if not df_raw.empty:
                                    fund_text = ""
                                    if not is_crypto_check:
                                        try:
                                            tk_info = yf.Ticker(ticker_symbol).info
                                            pe = tk_info.get('trailingPE', 0) or 0
                                            pbv = tk_info.get('priceToBook', 0) or 0
                                            roe = (tk_info.get('returnOnEquity', 0) or 0) * 100
                                            fund_text = f"- Fundamental: P/E {pe:.1f}x | PBV {pbv:.1f}x | ROE {roe:.1f}%\n"
                                        except: pass

                                    if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.get_level_values(0)
                                    df_hist = df_raw['Close'].dropna()
                                    if len(df_hist) >= 20:
                                        c_price = float(df_hist.iloc[-1])
                                        ma20 = float(df_hist.tail(20).mean())
                                        
                                        live_context += f"--- {tipe_aset} {tk} ---\n"
                                        live_context += f"- Harga Terakhir: {mata_uang} {c_price:,.0f} (Tren: {'Uptrend' if c_price>ma20 else 'Downtrend'})\n"
                                        live_context += fund_text
                                        
                                        # B. Tarik Berita Terkini via Google RSS
                                        try:
                                            q_news = f"{tk}+kripto" if is_crypto_check else f"{tk}+saham"
                                            feed = feedparser.parse(requests.get(f"https://news.google.com/rss/search?q={q_news}&hl=id&gl=ID&ceid=ID:id", headers={'User-Agent': 'Mozilla/5.0'}, timeout=3).content)
                                            if feed.entries:
                                                live_context += f"- Top Berita Terkini ({tk}):\n"
                                                for entry in feed.entries[:3]:
                                                    live_context += f"  * {entry.title}\n"
                                        except: live_context += "- (Tidak ada berita mayor terdeteksi hari ini)\n"
                                        
                                        live_context += "\n"
                                        valid_count += 1
                            except: pass

                    system_prompt = f"""Anda adalah 'Omni-Quant V6', Manajer Hedge Fund Institusional dan Penasihat Kekayaan Pribadi level dunia. Klien VVIP Anda bernama {nama_tampil}.

[KONDISI MAKRO GLOBAL]
{macro_context}
[DATA DOMPET/PORTOFOLIO KLIEN]
{portfolio_context}
[DATA SCREENER/RADAR SAHAM]
{screener_context}
[DATA TICKER SPESIFIK & BERITA]
{live_context}

INSTRUKSI MUTLAK (BACA BAIK-BAIK):
1. JIKA KLIEN MEMINTA EVALUASI PORTOFOLIO: Baca bagian [DATA DOMPET]. Beritahu dia saham mana yang untung/rugi, lalu berikan rekomendasi konkrit (mana yang harus di Hold, mana yang segera Cut Loss).
2. JIKA KLIEN MINTA CARIKAN SAHAM: Baca bagian [DATA SCREENER]. Berikan 1-3 rekomendasi terbaik yang masuk akal beserta alasannya (RSI oversold, dll).
3. JIKA KLIEN TANYA SAHAM SPESIFIK (Misal "Analisis BUMI"): Baca bagian [DATA TICKER & BERITA]. Analisis teknikalnya, dan pastikan Anda MENYEBUTKAN sentimen berita terkininya (jika ada) untuk menjawab alasan kenaikan/penurunannya.
4. JIKA KLIEN BERTANYA TEORI: Jawab sebagai Mentor yang edukatif dan mudah dipahami.
5. JANGAN PERNAH MENGARANG HARGA. Gunakan semua data di atas. Bahasa Indonesia profesional, tajam, dan memiliki empati terhadap uang klien.

Pertanyaan Klien: {prompt}"""
                    
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
                                    except ValueError: teks_balasan = "Mohon maaf, sistem memblokir respons karena alasan keamanan kata kunci."
                                    st.markdown(teks_balasan)
                                    st.session_state.messages.append({"role": "assistant", "content": teks_balasan})
                                    sukses = True
                                    break 
                            except Exception as e:
                                log_error += f"[{nama_model} gagal] "
                                continue 
                        if not sukses:
                            st.error(f"⚠️ Server AI sedang sibuk. Log teknis: {log_error}")
                    except Exception as e:
                        st.error(f"Kesalahan internal: {e}")
        st.rerun() 
