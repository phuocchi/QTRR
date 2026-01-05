import streamlit as st
import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime
from io import BytesIO
import random

st.set_page_config(
    page_title="Danh mục xếp hạng",
    page_icon="Mega.jpg",  
    layout="wide"
)



# --- Load dữ liệu ---
file_path = os.path.join("result", "summary.xlsx")

@st.cache_data
def load_data():
    return pd.read_excel(file_path)

df = load_data()


# --- Cấu hình trang ---
# st.set_page_config đã được gọi ở trên (nếu chưa thì gọi ở đây, nhưng code cũ đã có)

# --- Tạo Tabs chính ---
tab1, tab2 = st.tabs(["🔍 Danh mục xếp hạng", "⚠️ Cảnh báo rủi ro"])

with tab1:
    # --- Logo + tiêu đề căn giữa ---
    logo_path = Path("Mega2.png") 
    if logo_path.exists():
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col3:   # căn giữa ảnh
            st.image(str(logo_path), width=720)

    st.markdown(
        "<h1 style='text-align: center;'>DANH MỤC XẾP HẠNG</h1>",
        unsafe_allow_html=True
    )

    # --- Thanh tìm kiếm nhiều mã ---
    search_input = st.text_input("Nhập mã cổ phiếu (ví dụ: ACB, HDB, CTG...):")
    tickers = [x.strip().upper() for x in search_input.replace(" ", ",").split(",") if x.strip()]

    # --- Bộ lọc theo Model ---
    model_filter = st.selectbox("Chọn mô hình:", ["Tất cả", "Ngân hàng", "Phi tài chính", "Chứng khoán", "Bảo hiểm"])

    # --- Bộ lọc theo Grade ---
    # Kiểm tra cột "Điểm" có tồn tại không để tránh lỗi nếu file excel chưa đúng format
    if "Điểm" in df.columns:
        grade_options = sorted(df["Điểm"].unique())
    else:
        grade_options = []
        
    grade_filter = st.multiselect("Chọn điểm:", options=grade_options)

    # --- Slider chọn số lượng hiển thị ---
    top_n = st.slider("Số lượng tối đa muốn hiển thị:", 30, 300, 50)

    # Áp dụng filter
    filtered = df.copy()
    if tickers:
        filtered = filtered[filtered["Mã"].isin(tickers)]
        
    if model_filter != "Tất cả":
        filtered = filtered[filtered["Mô hình"] == model_filter]

    if grade_filter:
        filtered = filtered[filtered["Điểm"].isin(grade_filter)]

    # --- Hiển thị kết quả ---
    st.write(f"Có {len(filtered)} kết quả sau khi lọc")
    st.dataframe(filtered.head(top_n), use_container_width=True)

    update_time = None
    if "Thời gian cập nhật" in df.columns:
        # Lấy giá trị đầu tiên không rỗng trong cột
        update_time = df["Thời gian cập nhật"].dropna().iloc[0] if not df["Thời gian cập nhật"].dropna().empty else None

    if not update_time:
        update_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    st.markdown(f"**Cập nhật lần cuối:** {update_time}")

    from io import BytesIO

    # --- Xuất Excel ---
    if not filtered.empty:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            filtered.to_excel(writer, index=False, sheet_name="KQ")

        st.download_button(
            label="Tải kết quả lọc về Excel",
            data=buffer.getvalue(),
            file_name="ket_qua_loc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with tab2:
    st.markdown("<h2 style='text-align: center; color: #d9534f;'>⚠️ CẢNH BÁO RỦI RO & NHẬN DIỆN SỚM</h2>", unsafe_allow_html=True)
    
    # --- Selector Nhóm Cảnh Báo ---
    warning_group = st.selectbox(
        "Chọn nhóm cảnh báo:",
        ["Tăng trưởng ảo", "BCTC âm", "Danh sách chứng khoán không được phép GDKQ", "So sánh ngành", "Khối lượng giao dịch"]
    )
#   "Nội bộ doanh nghiệp", "Thanh khoản cổ phiếu"
    # --- Data Generators ---
    @st.cache_data
    def load_qtrr_data():
        try:
            path = os.path.join("result", "qtrr_output1.xlsx")
            return pd.read_excel(path)
        except Exception as e:
            # # Fallback to original file if output1 not found
            # try:
            #     path = os.path.join("result", "qtrr_output.xlsx")
            #     return pd.read_excel(path)
            # except Exception as e:
            #     st.error(f"Không tìm thấy file dữ liệu: {e}")
            return pd.DataFrame()

    def get_financial_warnings(view_mode, selected_year=None, selected_quarters=None):
        df_qtrr = load_qtrr_data()
        if df_qtrr.empty:
            return pd.DataFrame()

        # 1. Filter by Period Type

        if view_mode == "Năm":
            df_filtered = df_qtrr[df_qtrr["LengthReport"] == 5].copy()
        else:
            df_filtered = df_qtrr[df_qtrr["LengthReport"] != 5].copy()

        if not df_filtered.empty:
            # Sort by Ticker and Time Descending to Ensure Correct Lag Calculation
            df_filtered = df_filtered.sort_values(by=["Ticker", "KyBaoCao"], ascending=[True, False])
            
            # Logic: "Tăng trưởng ảo"
            # Condition: CFO < 0 AND Revenue > 0 for 2 consecutive periods (Quarter OR Year)
            df_filtered["Tăng trưởng ảo"] = "" # Default empty
            
            # Ensure needed columns exist
            cfo_col = "Lưu chuyển tiền thuần từ HĐKD"
            rev_col = "Doanh thu thuần"
            
            if cfo_col in df_filtered.columns and rev_col in df_filtered.columns:
                # Create boolean masks
                # Note: We need to handle potential non-numeric data if any, but assuming numeric from Excel
                condition_mask = (df_filtered[cfo_col] < 0) & (df_filtered[rev_col] > 0)
                
                # Group by Ticker and shift to get previous period's condition
                # Shift(-1) because we sorted Descending (Latest is index i, Previous is index i+1)
                condition_prev = df_filtered.groupby("Ticker")[cfo_col].shift(-1) < 0
                condition_prev_rev = df_filtered.groupby("Ticker")[rev_col].shift(-1) > 0
                
            # Combined Check: Current Met AND Previous Met
                final_mask = condition_mask & condition_prev & condition_prev_rev
                
                df_filtered.loc[final_mask, "Tăng trưởng ảo"] = "🚩"

            # 2. Filter by User Selection (After calculating indicators)
            if selected_year:
                df_filtered = df_filtered[df_filtered["YearReport"] == selected_year]
            
            if view_mode == "Quý" and selected_quarters:
                df_filtered = df_filtered[df_filtered["KyBaoCao"].isin(selected_quarters)]

            # If no specific filter for period, we assume user wants to see *something*. 
            # Original behavior was "Latest". If we add filters, we show matched.
            # If default (no year/quarter passed), maybe default to latest? 
            # But the UI will provide defaults.

        
        # 3. Select and Rename Columns
        cols_to_show = ["Ticker", "KyBaoCao", "Tăng trưởng ảo", 'Lưu chuyển tiền thuần từ HĐKD', "Doanh thu thuần", "Cổ đông của công ty mẹ", "LNST"]
        # Ensure columns exist
        cols_existing = [c for c in cols_to_show if c in df_filtered.columns]
        
        df_final = df_filtered[cols_existing].rename(columns={
            "Cổ đông của công ty mẹ": "Lợi nhuận của công ty mẹ",
            "Ticker": "Mã CP"
        })
        
        
        return df_final

    def get_cash_flow_warnings(view_mode, metrics=None):
        if metrics is None:
            metrics = ["Lưu chuyển tiền thuần từ HĐKD"]

        df_qtrr = load_qtrr_data()
        if df_qtrr.empty:
            return pd.DataFrame()

        # 1. Filter by Period Type
        if view_mode == "Năm":
            df_filtered = df_qtrr[df_qtrr["LengthReport"] == 5].copy()
        else:
            df_filtered = df_qtrr[df_qtrr["LengthReport"] != 5].copy()

        if df_filtered.empty:
            return pd.DataFrame()

        # 2. Logic: Warning Flags for each metric
        # Sort by Ticker and Time Descending for correct shift
        df_filtered = df_filtered.sort_values(by=["Ticker", "KyBaoCao"], ascending=[True, False])
        
        # We will collect result columns here
        cols_to_show = ["Ticker", "KyBaoCao"]
        
        for metric in metrics:
            if metric not in df_filtered.columns:
                continue
                
            # Create Flags for this metric
            g = df_filtered.groupby("Ticker")[metric]
            
            # Conditions (Negative value)
            # Handle potential non-numeric gracefully? Assuming numeric from Excel.
            s0 = df_filtered[metric] < 0                  # Current Period < 0
            s1 = g.shift(-1) < 0                           # Previous Period < 0
            s2 = g.shift(-2) < 0                           # 2 Periods ago < 0
            
            # FillNa
            s1 = s1.fillna(False)
            s2 = s2.fillna(False)
            
            flag_col_name = f"{metric}" # Column header will be the metric name, content is flags
            
            df_filtered[flag_col_name] = "" # Default empty
            
            # Assign flags
            df_filtered.loc[s0, flag_col_name] = "🚩"
            df_filtered.loc[s0 & s1, flag_col_name] = "🚩🚩"
            df_filtered.loc[s0 & s1 & s2, flag_col_name] = "🚩🚩🚩"
            
            cols_to_show.append(flag_col_name)

        # 3. Filter to keep only the latest report for each Ticker
        df_filtered = df_filtered.drop_duplicates(subset=["Ticker"], keep='first')

        # 4. Select Columns
        # cols_to_show already built
        existing_cols = [c for c in cols_to_show if c in df_filtered.columns]
        
        df_final = df_filtered[existing_cols].rename(columns={"Ticker": "Mã CP"})
        
        return df_final

    def get_internal_warnings():
        tickers = ["VIC", "VHM", "VRE", "MSN", "TCB", "VPB", "MBB"]
        data = []
        for ticker in tickers:
            data.append({
                "Mã CP": ticker,
                # "Sàn": random.choice(["HOSE", "HNX", "UPCOM"]),
                # "Mô hình": random.choice(["Ngân hàng", "Chứng khoán", "Bảo hiểm", "Phi tài chính"]),
                # "Giao dịch nội bộ": random.choice(["Mua ròng", "Bán ròng", "Không có"]),
                # "Thay đổi nhân sự chủ chốt": random.choice(["Ổn định", "Biến động", "Từ nhiệm"]),
                "Sở hữu nhà nước": random.choice(["0%", "30%", "51%", "90%"])
            })
        return pd.DataFrame(data)

    def get_liquidity_warnings():
        tickers = ["FLC", "ROS", "HAI", "AMD", "GAB", "ART", "KLF"] # Example tickers
        data = []
        for ticker in tickers:
            data.append({
                "Mã CP": ticker,
                "Sàn": random.choice(["HOSE", "HNX", "UPCOM"]),
                "Mô hình": random.choice(["Ngân hàng", "Chứng khoán", "Bảo hiểm", "Phi tài chính"]),
                "Khối lượng đột biến": random.choice(["Cao", "Trung bình", "Thấp"]),
                "Giá trị giao dịch trung bình (20p)": f"{random.randint(10, 500)} tỷ"
                
            })
        return pd.DataFrame(data)

    def get_margin_warnings():
        try:
            path = os.path.join("result1", "hose_stocks1.xlsx")
            df = pd.read_excel(path)
            if not df.empty:
                # Rename symbol to Mã CP for consistency
                if "symbol" in df.columns:
                    df = df.rename(columns={"symbol": "Mã CP"})
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Lỗi khi đọc file hose_stocks.xlsx: {e}")
            return pd.DataFrame()

    def get_volume_warnings(selected_date=None):
        try:
            # Try to locate the csv file
            path = os.path.join("Volume", "result", "volume_signal_daily.csv")
            if not os.path.exists(path):
                 st.error(f"Không tìm thấy file: {path}")
                 return pd.DataFrame()
            
            df = pd.read_csv(path)
            
            # Filter by date
            if selected_date and "time" in df.columns:
                 # Ensure 'time' column is string or datetime for comparison
                 # The CSV output showed '2025-02-14', etc.
                 df_filtered = df[df["time"] == str(selected_date)]
            else:
                 df_filtered = df
            
            if df_filtered.empty:
                return pd.DataFrame()

            # Rename columns
            rename_map = {
                "symbol": "Mã CP",
                "time": "Ngày",
                "volume": "Khối lượng",
                "vol_ma20": "TB 20 phiên",
                "vol_ma50": "TB 50 phiên",
                "vol_ma100": "TB 100 phiên",
                "vol_ma200": "TB 200 phiên",
                "vol_vs_ma20_pct": "% Tăng, giảm so với TB20",
                "vol_vs_ma50_pct": "% Tăng, giảm so với TB50",
                "vol_vs_ma100_pct": "% Tăng, giảm so với TB100",
                "vol_vs_ma200_pct": "% Tăng, giảm so với TB200",
                "flag_ma20": "Flag MA20",
                "flag_ma50": "Flag MA50",
                "flag_ma100": "Flag MA100",
                "flag_ma200": "Flag MA200",
                "flag_break_vol_100": "Đột biến Vol 100",
                "flag_break_vol_200": "Đột biến Vol 200"
            }
            # Select relevant columns
            cols_to_show = ["symbol", "time", "volume", "vol_vs_ma20_pct", "vol_vs_ma50_pct", "vol_vs_ma100_pct", "vol_vs_ma200_pct", "flag_break_vol_100", "flag_break_vol_200"]
            existing_cols = [c for c in cols_to_show if c in df.columns]
            
            df_final = df_filtered[existing_cols].rename(columns=rename_map)
            return df_final

        except Exception as e:
            st.error(f"Lỗi khi đọc file volume_signal_daily.csv: {e}")
            return pd.DataFrame()

    def get_industry_comparison(view_mode, selected_year, selected_quarters, selected_industries):
        df_qtrr = load_qtrr_data()
        if df_qtrr.empty or "Nganh" not in df_qtrr.columns:
            st.warning("Dữ liệu quản trị rủi ro chưa có thông tin Ngành. Vui lòng cập nhật dữ liệu.")
            return pd.DataFrame()

        # 1. Base Filter
        if view_mode == "Năm":
            mask = (df_qtrr["LengthReport"] == 5)
        else:
            mask = (df_qtrr["LengthReport"] != 5)
            
        df_filtered = df_qtrr[mask].copy()

        # 2. Filter by Year
        if selected_year:
            df_filtered = df_filtered[df_filtered["YearReport"] == selected_year]
            
        # 3. Filter by Quarter (if applicable)
        if view_mode == "Quý" and selected_quarters:
             df_filtered = df_filtered[df_filtered["KyBaoCao"].isin(selected_quarters)] 

        # 4. Filter by Industry
        if selected_industries:
            df_filtered = df_filtered[df_filtered["Nganh"].isin(selected_industries)]

        if df_filtered.empty:
            return pd.DataFrame()

        # 5. Calculation: Rank and % Difference per Industry, per Period (Year+Quarter)
        # We process separately for each period present in the filtered data to ensure correct ranking
        
        result_dfs = []
        # Group by Time Period + Industry
        # Time Period Identifier: 'YearReport' + 'KyBaoCao'
        groups = df_filtered.groupby(['YearReport', 'KyBaoCao', 'Nganh'])
        
        for name, group in groups:
            g = group.copy()
            
            # --- Gross Margin ---
            if 'Biên lợi nhuận gộp' in g.columns:
                g['Rank BLN Gộp/Ngành'] = g['Biên lợi nhuận gộp'].rank(ascending=False, method='min')
                mean_gop = g['Biên lợi nhuận gộp'].mean()
                # % Diff: (Val - Mean) * 100 for absolute percentage point difference OR relative? 
                # " % chênh lệch ... so với trung bình" usually implies relative: (Val - Avg)/Avg
                # However for margins (percentages), usually simple diff is used.
                # Let's use simple diff for now: Val - Mean. If Val is 0.20 (20%) and Mean is 0.15 (15%), diff is 0.05 (5%).
                # User asked "% chênh lệch". I will output the raw difference which effectively is %.
                g['% BLN Gộp vs TB Ngành'] = (g['Biên lợi nhuận gộp'] - mean_gop) * 100 # Convert to percentage points
                
            # --- Net Margin ---
            if 'Biên lợi nhuận ròng' in g.columns:
                g['Rank BLN Ròng/Ngành'] = g['Biên lợi nhuận ròng'].rank(ascending=False, method='min')
                mean_rong = g['Biên lợi nhuận ròng'].mean()
                g['% BLN Ròng vs TB Ngành'] = (g['Biên lợi nhuận ròng'] - mean_rong) * 100

            result_dfs.append(g)
            
        if result_dfs:
            df_final = pd.concat(result_dfs)
            
            # --- Cleaning: Remove rows with no valid margin data ---
            # Replace inf/-inf with NaN
            df_final.replace([np.inf, -np.inf], np.nan, inplace=True)
            
            # Drop rows where BOTH Gross and Net margins are NaN
            cols_to_check = [c for c in ['Biên lợi nhuận gộp', 'Biên lợi nhuận ròng'] if c in df_final.columns]
            if cols_to_check:
                df_final = df_final.dropna(subset=cols_to_check, how='all')
                
        else:
            df_final = pd.DataFrame()

        # Select columns
        cols_to_show = ["Ticker", "Nganh", "YearReport", "KyBaoCao", 
                        "Rank BLN Gộp/Ngành", "% BLN Gộp vs TB Ngành", "Biên lợi nhuận gộp",
                        "Rank BLN Ròng/Ngành", "% BLN Ròng vs TB Ngành", "Biên lợi nhuận ròng"]
        cols_existing = [c for c in cols_to_show if c in df_final.columns]
        
        return df_final[cols_existing].rename(columns={"Ticker": "Mã CP"})


    # --- Filters ---
    search_input_risk = st.text_input("Nhập mã cổ phiếu (ví dụ: VIC, VHM...):", key="risk_ticker_filter")
    risk_tickers = [x.strip().upper() for x in search_input_risk.replace(" ", ",").split(",") if x.strip()]

    # Global filters for common tabs
    # (Only show if NOT "So sánh ngành" because that tab has its own specific logic?)
    # or Keep them? The user said "t có thể chọn được fillter của từng quý từng năm và từng ngành"
    
    if warning_group != "So sánh ngành":
        c_filter_1, c_filter_2 = st.columns(2)
        with c_filter_1:
            selected_exchanges = st.multiselect("Lọc theo Sàn:", ["HOSE", "HNX", "UPCOM"], default=[])
        with c_filter_2:
            selected_sectors = st.multiselect("Lọc theo ngành:", ["Ngân hàng", "Chứng khoán", "Bảo hiểm", "Phi tài chính"], default=[])

    # --- Display Logic ---
    df_display = pd.DataFrame()
    df_display_renamed = pd.DataFrame()

    if warning_group == "Tăng trưởng ảo":
        st.info("Các cảnh báo liên quan đến Báo cáo tài chính, chất lượng lợi nhuận và dòng tiền.")
        
        # Filters for Financials
        raw_df = load_qtrr_data()
        
        col_y, col_q = st.columns(2)
        with col_y:
            view_mode = st.radio("Xem dữ liệu theo:", ["Quý", "Năm"], horizontal=True)
            
            # Filter available years based on View Mode
            if view_mode == "Năm":
                years_in_data = raw_df[raw_df["LengthReport"] == 5]["YearReport"].unique()
            else:
                years_in_data = raw_df[raw_df["LengthReport"] != 5]["YearReport"].unique()
                
            available_years = sorted(years_in_data, reverse=True) if len(years_in_data) > 0 else []
            selected_year = st.selectbox("Chọn Năm:", available_years, key="fin_year")

        
        selected_quarters = []
        with col_q:
            if view_mode == "Quý":
                 # Helper to get quarters for selected year
                 if "KyBaoCao" in raw_df.columns and "YearReport" in raw_df.columns:
                     q_df = raw_df[(raw_df["YearReport"] == selected_year) & (raw_df["LengthReport"] != 5)]
                     # Extract quarter numbers for UI (e.g., "2025_Q1" -> 1)
                     avail_q_nums = set()
                     for q_str in q_df["KyBaoCao"].dropna().unique():
                         if "_Q" in str(q_str):
                             try:
                                 q_num = int(str(q_str).split("_Q")[1])
                                 avail_q_nums.add(q_num)
                             except:
                                 pass
                     available_quarters = sorted(list(avail_q_nums), reverse=True)
                     
                     selected_q_nums = st.multiselect("Chọn Quý:", available_quarters, default=available_quarters[:1], key="fin_quarters")
                     # Convert back to string format for filtering
                     selected_quarters = [f"{selected_year}_Q{q}" for q in selected_q_nums]
            else:
                st.write("") # Spacer

        df_display = get_financial_warnings(view_mode, selected_year, selected_quarters)
        df_display_renamed = df_display.copy()

    elif warning_group == "BCTC âm":
        st.info("Cảnh báo âm liên tiếp cho các chỉ số tài chính (dữ liệu cập nhật mới nhất).")
        
        col_y, col_metrics = st.columns([1, 2])
        with col_y:
            view_mode = st.radio("Xem dữ liệu theo:", ["Quý", "Năm"], horizontal=True, key="cf_view_mode")
            
        with col_metrics:
            available_metrics = ["Lưu chuyển tiền thuần từ HĐKD", "Cổ đông của công ty mẹ", "LNST"]
            selected_metrics = st.multiselect(
                "Chọn chỉ số cảnh báo:", 
                available_metrics, 
                default=["Lưu chuyển tiền thuần từ HĐKD"]
            )
        
        if selected_metrics:
            df_display = get_cash_flow_warnings(view_mode, metrics=selected_metrics)
            df_display_renamed = df_display.copy()
        else:
            st.warning("Vui lòng chọn ít nhất một chỉ số.")
            df_display_renamed = pd.DataFrame()
        
    elif warning_group == "Nội bộ doanh nghiệp":
        st.info("Các cảnh báo về giao dịch cổ đông lớn, ban lãnh đạo và cơ cấu sở hữu.")
        df_display = get_internal_warnings()
        df_display_renamed = df_display.copy()
        
    elif warning_group == "Thanh khoản cổ phiếu":
        st.info("Các cảnh báo về dòng tiền, khối lượng giao dịch bất thường.")
        df_display = get_liquidity_warnings()
        df_display_renamed = df_display.copy()

    elif warning_group == "Danh sách chứng khoán không được phép GDKQ":
        df_display = get_margin_warnings()
        df_display_renamed = df_display.copy()

    elif warning_group == "So sánh ngành":
        st.info("So sánh hiệu quả hoạt động (Biên LN) của doanh nghiệp so với trung bình ngành.")
        
        # Load raw data to get unique values for filters
        raw_df = load_qtrr_data()
        
        col_y, col_q, col_i = st.columns(3)
        
        with col_y:
            view_mode = st.radio("Dữ liệu:", ["Quý", "Năm"], horizontal=True)
            
        # Get helper lists based on View Mode
        if "YearReport" in raw_df.columns:
            if view_mode == "Năm":
                years_in_data = raw_df[raw_df["LengthReport"] == 5]["YearReport"].unique()
            else:
                years_in_data = raw_df[raw_df["LengthReport"] != 5]["YearReport"].unique()
            available_years = sorted(years_in_data, reverse=True)
        else:
            available_years = []
            
        available_industries = sorted(raw_df["Nganh"].dropna().unique()) if "Nganh" in raw_df.columns else []
        
        with col_q:
             selected_year = st.selectbox("Chọn Năm:", available_years, key="ind_year")
             
             selected_quarters = []
             if view_mode == "Quý":
                 if "KyBaoCao" in raw_df.columns:
                     q_df = raw_df[(raw_df["YearReport"] == selected_year) & (raw_df["LengthReport"] != 5)]
                     
                     avail_q_nums = set()
                     for q_str in q_df["KyBaoCao"].dropna().unique():
                         if "_Q" in str(q_str):
                             try:
                                 q_num = int(str(q_str).split("_Q")[1])
                                 avail_q_nums.add(q_num)
                             except:
                                 pass
                     available_quarters = sorted(list(avail_q_nums), reverse=True)
                     
                     selected_q_nums = st.multiselect("Chọn Quý:", available_quarters, default=available_quarters[:1], key="ind_quarters")
                     selected_quarters = [f"{selected_year}_Q{q}" for q in selected_q_nums]

        with col_i:
             selected_industries_comp = st.multiselect("Chọn Ngành:", available_industries, default=[])

        if st.columns(1)[0].button("Tải dữ liệu so sánh"):
            df_display = get_industry_comparison(view_mode, selected_year, selected_quarters, selected_industries_comp)
            df_display_renamed = df_display.copy()

    elif warning_group == "Khối lượng giao dịch":
        st.info("Cảnh báo các mã có khối lượng giao dịch đột biến hoặc tín hiệu kỹ thuật về Volume.")
        
        # Load dates to populate filter
        try:
             path_vol = os.path.join("Volume", "result", "volume_signal_daily.csv")
             if os.path.exists(path_vol):
                 df_vol_raw = pd.read_csv(path_vol)
                 if "time" in df_vol_raw.columns:
                     available_dates = sorted(df_vol_raw["time"].unique(), reverse=True)
                     selected_date_vol = st.selectbox("Chọn Ngày GD:", available_dates)
                     
                     df_display = get_volume_warnings(selected_date_vol)
                     df_display_renamed = df_display.copy()
                 else:
                     st.warning("File dữ liệu Volume không có cột 'time'.")
             else:
                 st.error("Chưa có dữ liệu Volume (Volume/result/volume_signal_daily.csv).")
        except Exception as e:
            st.error(f"Lỗi: {e}")

    
    # --- Apply Filters (Common) ---
    if not df_display_renamed.empty:
        # 1. Filter by Ticker first
        if risk_tickers:
            if "Mã CP" in df_display_renamed.columns:
                df_display_renamed = df_display_renamed[df_display_renamed["Mã CP"].isin(risk_tickers)]
        
        # Logic to merge with main df to get Sàn/Mô hình if missing (SKIP for Ind Comparison as it has its own logic)
        if warning_group != "So sánh ngành":
            if (selected_exchanges or selected_sectors) and "Sàn" not in df_display_renamed.columns:
                 if "Mã CP" in df_display_renamed.columns and "Mã" in df.columns:
                    df_merged = df_display_renamed.merge(
                        df[["Mã", "Sàn", "Mô hình"]].drop_duplicates(),
                        left_on="Mã CP",
                        right_on="Mã",
                        how="left"
                    )
                    if "Sàn" in df_merged.columns:
                        df_display_renamed = df_merged

            if selected_exchanges and "Sàn" in df_display_renamed.columns:
                 df_display_renamed = df_display_renamed[df_display_renamed["Sàn"].isin(selected_exchanges)]
            if selected_sectors and "Mô hình" in df_display_renamed.columns:
                 df_display_renamed = df_display_renamed[df_display_renamed["Mô hình"].isin(selected_sectors)]
        
        # Specific filter for Margin Warning
        if warning_group == "Danh sách chứng khoán không được phép GDKQ" and "status" in df_display_renamed.columns:
             unique_statuses = df_display_renamed["status"].unique().tolist()
             selected_statuses = st.multiselect("Lọc theo trạng thái:", unique_statuses, default=unique_statuses)
             if selected_statuses:
                 df_display_renamed = df_display_renamed[df_display_renamed["status"].isin(selected_statuses)]

    # --- Custom Styling for Table ---
    def highlight_negative(val):
        if isinstance(val, (int, float)) and val < 0:
            return 'color: red'
        return ''

    def highlight_diff(val):
        if isinstance(val, (int, float)):
            if val > 0: return 'color: green'
            if val < 0: return 'color: red'
        return ''

    if not df_display_renamed.empty:
        styled_df = df_display_renamed.style
        
        if warning_group == "So sánh ngành":
             # Format specific columns
             format_dict = {
                 "Biên lợi nhuận gộp": "{:.2%}",
                 "Biên lợi nhuận ròng": "{:.2%}",
                 "% BLN Gộp vs TB Ngành": "{:+.2f} %",
                 "% BLN Ròng vs TB Ngành": "{:+.2f} %",
                 "Rank BLN Gộp/Ngành": "{:.0f}",
                 "Rank BLN Ròng/Ngành": "{:.0f}"
             }
             # Apply format to columns that exist
             cols_to_format = {k: v for k, v in format_dict.items() if k in df_display_renamed.columns}
             styled_df = styled_df.format(cols_to_format)
             
             # Highlight diffs
             subset_diff = [c for c in ["% BLN Gộp vs TB Ngành", "% BLN Ròng vs TB Ngành"] if c in df_display_renamed.columns]
             if subset_diff:
                 styled_df = styled_df.map(highlight_diff, subset=subset_diff)

        elif "Lợi nhuận của công ty mẹ" in df_display_renamed.columns:
            styled_df = styled_df.map(highlight_negative, subset=["Lưu chuyển tiền thuần từ HĐKD", "Lợi nhuận của công ty mẹ", "LNST"])
            styled_df = styled_df.format(thousands=",", precision=0)

        elif "Khối lượng" in df_display_renamed.columns:
             # Formatting for Volume tab
             format_dict_vol = {
                 "Khối lượng": "{:,.0f}",
                 "TB 20 phiên": "{:,.0f}",
                 "% Tăng, giảm so với TB20": "{:.2f}%",
                 "% Tăng, giảm so với TB50": "{:.2f}%",
                 "% Tăng, giảm so với TB100": "{:.2f}%",
                 "% Tăng, giảm so với TB200": "{:.2f}%"
             }
             styled_df = styled_df.format({k:v for k,v in format_dict_vol.items() if k in df_display_renamed.columns})
             
             # Highlight breakout
             if "Đột biến Vol 100" in df_display_renamed.columns:
                 def highlight_true(val):
                     return 'background-color: #d4edda; color: #155724' if val == True or val == "True" else ''
                 styled_df = styled_df.map(highlight_true, subset=["Đột biến Vol 100"])

             # Highlight % changes
             def highlight_volume_change(val):
                 if isinstance(val, (int, float)):
                     if val > 100:
                         return 'color: #800080; font-weight: bold;' # Purple for > 100%
                     elif val > 50:
                         return 'color: #0000FF; font-weight: bold;' # Dark Green for > 50%
                     elif val > 20:
                         return 'color: #008000;' # Lime Green for > 20%
                     elif val < 0:
                         return 'color: #dc3545;' # Red for negative
                 return ''
             
             vol_pct_cols = [c for c in df_display_renamed.columns if "% Tăng" in c]
             if vol_pct_cols:
                 styled_df = styled_df.map(highlight_volume_change, subset=vol_pct_cols)

        st.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True
        )

        # --- Xuất Excel ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_display_renamed.to_excel(writer, index=False, sheet_name="Data")

        st.download_button(
            label="Tải dữ liệu về Excel",
            data=buffer.getvalue(),
            file_name=f"QTRR_{warning_group}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


