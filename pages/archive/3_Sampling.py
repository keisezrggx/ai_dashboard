import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import logging

# from backend.kula.chatbot_optimized import ChatbotOptimized
from streamlit_chatbox import *
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder
from datetime import datetime, timedelta

logging.getLogger('streamlit.runtime.scriptrunner').setLevel(logging.ERROR)

CURRENT_THEME = "light" 
IS_DARK_THEME = False
st.set_page_config(layout="wide")


# -------------------------------------------------
# Cached data loader — avoids re-reading CSVs on every Streamlit re-render
# -------------------------------------------------
@st.cache_data(ttl=3600)
def load_csv(path, **kwargs):
    """Load a CSV once and cache the result for 1 hour."""
    return pd.read_csv(path, **kwargs)


# -------------------------------------------------
# Reusable AgGrid renderer — replaces 8 repeated blocks
# -------------------------------------------------
def render_aggrid(df, height=400):
    """Build and display an AgGrid table with standard options."""
    gb = GridOptionsBuilder.from_dataframe(df)
    for col in df.columns:
        gb.configure_column(col, filter=False, sortable=True, resizable=True)
    gb.configure_pagination()
    AgGrid(df, gridOptions=gb.build(), height=height)

# team = st.sidebar.radio('Team', ['QC'])
team = 'QC'

if team == 'QC':
    st.sidebar.header("Adjust Data")

    # page = st.sidebar.selectbox("Pages", ["Agent Sample", "Hotline Calibration"])
    page = 'Hotline Calibration'



# ============ Fungsi Global Week of Month ============
def week_of_month(date):
    days_in_month = pd.Period(date, freq='M').days_in_month
    week_length = days_in_month / 4
    week_num = int((date.day - 1) // week_length) + 1
    return min(week_num, 4)


def aggregate_side(df, date_col, granularity, csat_col):
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    # Force numeric
    for c in ['Total Responden', 'Total Rating', 'CSAT [Before]', 'CSAT [After]']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # Period bucketing
    if granularity == 'Daily':
        df['Period'] = df[date_col].dt.date
        grouped = (
            df.groupby('Period').
            agg({csat_col: 'mean'})
            .reset_index()
            .rename(columns={'Period': 'Date'})
        )
        return grouped[['Date', csat_col]]

    if granularity == 'Weekly':
        df['Period'] = df[date_col].dt.to_period('W').dt.start_time
    elif granularity == 'Monthly':
        df['Period'] = df[date_col].dt.to_period('M').dt.to_timestamp()
    else:
        df['Period'] = df[date_col]

    def compute_period(g):
        out = {}
        # Weighted average by respondents (fallback to mean if missing)
        if csat_col in g.columns and 'Total Responden' in g.columns and g['Total Responden'].sum() > 0:
            out[csat_col] = (g[csat_col] * g['Total Responden']).sum() / g['Total Responden'].sum()
        else:
            out[csat_col] = g[csat_col].mean() if csat_col in g.columns else np.nan
        return pd.Series(out)
    
    grouped = (
        df.groupby('Period')
        .apply(compute_period)
        .reset_index()
        .rename(columns={'Period': 'Date'})
    )
    
    return grouped[['Date', csat_col]]

def aggregate_csat_dual(df_before, df_after, date_col, granularity):
    if 'CSAT [Before]' not in df_before.columns:
        raise ValueError("df_before must contain 'CSAT [Before]' column")
    if 'CSAT [After]' not in df_after.columns:
        raise ValueError("df_after must contain 'CSAT [After]' column")
    
    before_g = aggregate_side(df_before, date_col, granularity, 'CSAT [Before]')
    after_g = aggregate_side(df_after, date_col, granularity, 'CSAT [After]')

    combined = (
        pd.merge(before_g, after_g, on='Date', how='outer')
        .sort_values('Date')
        .reset_index(drop=True)
    )

    return combined[['Date', 'CSAT [Before]', 'CSAT [After]']]

# Function to return the ratio weekly monthly count
def aggregation_ratio(df, date_col, granularity):
    if df is None or df.empty:
        return pd.DataFrame(columns=['Date', 'Robot Success ratio'])

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    for c in ['Connected to robot', 'Number of exit queues', 'Total handle robot']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    if granularity == 'Daily':
        df['Period'] = df[date_col].dt.normalize()
    elif granularity == 'Weekly':
        df['Period'] = df[date_col].dt.to_period('W').dt.start_time
    elif granularity == 'Monthly':
        df['Period'] = df[date_col].dt.to_period('M').dt.to_timestamp()
    else:
        df['Period'] = df[date_col]

    # hitung ratio per period
    grouped = df.groupby('Period').agg({
        'Connected to robot': 'sum',
        'Number of exit queues': 'sum',
        'Total handle robot': 'sum'
    }).reset_index()

    # Vectorized ratio — avoids slow row-by-row .apply(axis=1)
    grouped['Robot Success ratio'] = np.where(
        grouped['Connected to robot'] > 0,
        (grouped['Total handle robot'] - grouped['Number of exit queues'])
            / grouped['Connected to robot'] * 100,
        np.nan
    )

    # grouped['Robot Success ratio'] = (
    #     (grouped['Total handle robot'] - grouped['Number of exit queues']) /
    #     grouped['Connected to robot'] * 100
    # )

    grouped = grouped.sort_values('Period').reset_index(drop=True)

    return grouped[['Period', 'Robot Success ratio']].rename(columns={'Period': 'Date'})


    
def aggregate_sum(df, date_col, granularity, agg_dict):
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    if granularity == 'Daily':
        df['Period'] = df[date_col].dt.date
    elif granularity == 'Weekly':
        df['Period'] = df[date_col].dt.to_period('W').dt.start_time
    elif granularity == 'Monthly':
        df['Period'] = df[date_col].dt.to_period('M').dt.to_timestamp()
    else:
        df['Period'] = df[date_col]

    result = df.groupby('Period').agg(agg_dict).reset_index()
    return result.rename(columns={'Period': 'Date'})


# ============ Multiselect filter date for bad surey and like dislike table ============
def sidebar_filters():
    company_filter = st.sidebar.multiselect(
        'Select Company',
        options=['ASI','AFI','No Differentiated','AFI/ASI'],
        default=['ASI']
    )
    
    date_mode = st.sidebar.radio('Date Mode', ['Range','Single'], index=0)

    selected_date = None

    if date_mode == 'Single':
        selected_date = st.sidebar.date_input(
            'Selected Date',
            value=pd.to_datetime('today').date(),
            key='global_date'
        )

    return company_filter, date_mode, selected_date


# ============ Function to show Weeks and Months ============
def aggregate_table_with_granularity(
        df, category_col, value_col=None, date_col=None, granularity=None, start_date=None, end_date=None
):
    df = df.copy()

    # Convert to datetime FIRST, then apply date filter
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    if start_date is not None and end_date is not None:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]

    if df.empty:
        return pd.DataFrame(columns=[category_col, 'Total'])

    # ==== Tentukan granularity ====
    if granularity == 'Weekly':
        # Buat daftar rentang minggu berdasarkan start_date dan end_date
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Buat list awal minggu
        week_starts = []
        current_start = start_date
        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=6), end_date)
            week_starts.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)

        # Buat kolom PeriodRaw dan Period (range tanggal)
        def get_week_label(d):
            for ws, we in week_starts:
                if ws <= d <= we:
                    if ws.month == we.month:
                        return f"{ws.day:02d}-{we.day:02d} {ws.strftime('%b')}"
                    else:
                        # kalau minggu melewati pergantian bulan
                        return f"{ws.day:02d} {ws.strftime('%b')} - {we.day:02d} {we.strftime('%b')}"
            return None

        df['PeriodRaw'] = df[date_col].apply(lambda d: next(ws for ws, we in week_starts if ws <= d <= we))
        df['Period'] = df[date_col].apply(get_week_label)

    elif granularity == 'Monthly':
        df['PeriodRaw'] = df[date_col].dt.to_period('M').dt.to_timestamp()
        df['Period'] = df['PeriodRaw'].dt.strftime('%b %Y')
    else:
        df['PeriodRaw'] = df[date_col].dt.normalize()
        df['Period'] = df['PeriodRaw'].dt.strftime('%Y-%m-%d')

    # ==== Konversi value_col ke numeric ====
    if value_col is not None and value_col in df.columns:
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)

    # ==== Making sure the category_col is list ====
    if isinstance(category_col, str):
        group_cols = [category_col, 'PeriodRaw','Period']
    elif isinstance(category_col, list):
        group_cols = category_col + ['PeriodRaw','Period']
    else:
        raise ValueError("category_col should be a string or a list of strings")

    # ==== Aggregasi ====
    if value_col is None:
        agg_df = (
            df.groupby(group_cols)
            .size()
            .reset_index(name='Total Sample')
        )
    else:
        agg_df = (
            df.groupby(group_cols)[value_col]
            .sum()
            .reset_index(name='Total Sample')
        )

    # ==== Pivot ====
    pivot = agg_df.pivot_table(
        index=category_col, 
        columns='Period', 
        values='Total Sample', 
        aggfunc='sum', 
        fill_value=0
    )

    # Urutkan kolom sesuai PeriodRaw
    period_order = agg_df[['PeriodRaw', 'Period']].drop_duplicates().sort_values('PeriodRaw')
    ordered_cols = [c for c in period_order['Period'] if c in pivot.columns]
    pivot = pivot[ordered_cols]

    # Tambah total
    pivot['Total'] = pivot.select_dtypes(include=[np.number]).sum(axis=1)
    pivot = pivot.sort_values('Total', ascending=False).reset_index()

    pivot.columns = pd.Index(pivot.columns).map(str)
    pivot = pivot.loc[:, ~pivot.columns.duplicated()]

    return pivot


def calculate_checker_accuracy(df):
    df = df.copy()  # Prevent mutating the caller's DataFrame
    # cari semua kolom yang dimulai dengan 'Count'
    count_cols = [col for col in df.columns if col.startswith("Count")]
    
    # bikin kolom baru = total kesalahan di 1 baris
    df["Total_Kesalahan"] = df[count_cols].sum(axis=1)
    
    # groupby per checker
    result = (
        df.groupby("Checker")
        .agg(
            Total_Tagging=("Checker", "count"),
            Kesalahan=("Total_Kesalahan", "sum")
        )
        .reset_index()
    )
    
    # hitung akurasi
    result["Accuracy"] = (result["Total_Tagging"] - result["Kesalahan"]) / result["Total_Tagging"] * 100
    
    return result


def aggregate_checker_errors(df):
    count_cols = [
        'Count Hasil ASR',
        'Count Hasil Pemeriksaan Kualitas',
        'Count Efektif',
        'Count Kejelasan Suara',
        'Count Kelengkapan Rekaman',
        'Count Revisi Text'
    ]
    df_checker = df.groupby('Checker')[count_cols].sum().reset_index()
    return df_checker, count_cols

def highlight_diff_words(original, revised):
    """
    Mengembalikan string HTML yang menandai kata-kata berbeda dalam `revised` dibandingkan `original` dengan warna merah.
    """
    original_words = original.split()
    revised_words = revised.split()
    s = difflib.SequenceMatcher(None, original_words, revised_words)
    result = []

    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == "equal":
            result.extend(revised_words[j1:j2])
        elif tag in ("replace", "insert"):
            for word in revised_words[j1:j2]:
                result.append(f"<span style='color: red'>{word}</span>")
        elif tag == "delete":
            continue  # tidak perlu menampilkan kata yang dihapus

    return " ".join(result)

# 2 screenshots path
def build_screenshot_path(filename: str):
    filename = str(filename).strip()
    if not filename or filename == '-' or filename.lower() == 'nan':
        return None
    # return f'screenshots/{filename}'
    return f'screenshots/{filename}'

# showing 2 screenshots side by side
def show_image(path: str):
    if not path:
        st.error('Image Restricted.')
        return
    try:
        st.image(path)
    except Exception as e:
        st.info('No image.')
    

# ==== Scorecard Style ====
def styled_metric(label, value, delta, delta_color="normal"):
    delta_symbol = "↑" if delta_color == "normal" else ("↑" if delta_color == "inverse" else "") #↓
    delta_color_code = {
        "normal": "#28a745",     # Merah
        "inverse": "#dc3545",    # hijau
        "off": "#999999"         # abu netral
    }.get(delta_color, "#000000")

    delta_text = f"{delta_symbol} {abs(delta):,} data" if delta_color != "off" else "-"

    html = f"""
    <div style="
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.1);
        background-color: #fff;
        display: flex;
        flex-direction: column;
        gap: 6px;
    ">
        <div style="font-size: 14px; font-weight: semi-bold; color: #444; text-align: left;">
            {label}
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end;">
            <div style="font-size: 24px; font-weight: bold; color: #111;">{value}</div>
            <div style="font-size: 14px; font-weight: bold; color: {delta_color_code};">{delta_text}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

df_sampling = load_csv('dataset_qc/kalib_sampling.csv', parse_dates=['Tanggal Sampling'])

# ==== Layout ====
st.title("Sampling Data")

latest_date = df_sampling["Tanggal Sampling"].max()
latest_date_str = latest_date.strftime("%d/%m/%Y")

st.markdown(f"##### Updated Till {latest_date_str}")

# ==== Filter Tanggal ====
min_date = df_sampling['Tanggal Sampling'].min().date()
max_date = df_sampling['Tanggal Sampling'].max().date()

start_date, end_date = st.sidebar.date_input(
    "Pilih Rentang Tanggal",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Konversi ke datetime
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

# Filter DataFrame berdasarkan tanggal
df_sampling = df_sampling[
    (df_sampling['Tanggal Sampling'] >= start_date) &
    (df_sampling['Tanggal Sampling'] <= end_date)
]

# Compute .str.upper() ONCE — reuse everywhere instead of calling 6 times
red_label_upper = df_sampling['Red Label'].str.upper()

# ==== Filter RED LABEL ====
df_merah = df_sampling[
    red_label_upper.isin(["MERAH", "TEXT"])
]

# ==== Hitung Persentase ====
total_data = len(df_sampling)
total_merah = len(df_merah)
persen_merah = (total_merah / total_data) * 100
persen_non_merah = 100 - persen_merah

# ==== Scorecards ====
with st.container():

    # Hitung total
    total_data = len(df_sampling)
    total_merah = len(df_merah)
    total_tidak_merah = total_data - total_merah

    # Ambil tanggal terakhir dan hari sebelumnya
    last_selected_date = end_date.date()
    day_before_last = (end_date - pd.Timedelta(days=1)).date()

    # Filter data Sampling untuk hari terakhir
    df_this_day = df_sampling[df_sampling['Tanggal Sampling'].dt.date == last_selected_date]
    df_last_day = df_sampling[df_sampling['Tanggal Sampling'].dt.date == day_before_last]

    # === Jumlah Hari Ini (use cached upper) ===
    total_this_day = df_this_day.shape[0]
    this_day_upper = df_this_day['Red Label'].str.upper()
    merah_this_day = this_day_upper.isin(['MERAH', 'TEXT']).sum()

    non_merah_this_day = (~this_day_upper.isin(['MERAH'])).sum()

    # === Delta ===
    delta_total = total_this_day
    delta_merah = merah_this_day
    delta_non_merah = non_merah_this_day

    # === Warna Panah ===
    delta_color_total = "normal"
    delta_color_non_merah = "normal"
    delta_color_merah = "inverse"

    # Tampilkan scorecard
    cols = st.columns(3)
    with cols[0]:
        styled_metric("TOTAL SAMPLING", f"{total_data:,} data", delta_total, delta_color_total)
    with cols[1]:
        styled_metric("MERAH & TEXT", f"{total_merah:,} data", delta_merah, delta_color_merah)
    with cols[2]:
        styled_metric("TIDAK MERAH", f"{total_tidak_merah:,} data", delta_non_merah, delta_color_non_merah)

# ==== Weekly Trend Line Chart ===
df_sampling['Week'] = df_sampling['Tanggal Sampling'].dt.to_period('W').dt.start_time

# Pisahkan berdasarkan Red Label (use cached upper)
df_merah = df_sampling[red_label_upper.loc[df_sampling.index] == "MERAH"]
df_text = df_sampling[red_label_upper.loc[df_sampling.index] == "TEXT"]

# Hitung jumlah per minggu
df_merah_weekly = df_merah.groupby('Week').size().reset_index(name='Jumlah')
df_text_weekly = df_text.groupby('Week').size().reset_index(name='Jumlah')

# Pastikan kolom 'Week' jadi datetime agar bisa digabung
df_merah_weekly['Week'] = pd.to_datetime(df_merah_weekly['Week'])
df_text_weekly['Week'] = pd.to_datetime(df_text_weekly['Week'])

# ==== Buat Figure manual ====
fig_line = go.Figure()

# Tambahkan garis MERAH
fig_line.add_trace(go.Scatter(
    x=df_merah_weekly['Week'],
    y=df_merah_weekly['Jumlah'],
    mode='lines+markers+text',
    name='MERAH',
    line=dict(color='#dc3545', width=2, dash='solid'),
    text=df_merah_weekly['Jumlah'],
    textposition='top center'
))

# Tambahkan garis TEXT (dashed)
fig_line.add_trace(go.Scatter(
    x=df_text_weekly['Week'],
    y=df_text_weekly['Jumlah'],
    mode='lines+markers+text',
    name='TEXT',
    line=dict(color='#f4a261', width=2, dash='dash'),
    text=df_text_weekly['Jumlah'],
    textposition='top center'
))

# === Hitung rata-rata MERAH saja ===
avg_merah = df_merah_weekly['Jumlah'].mean()

# Tambahkan garis rata-rata MERAH
fig_line.add_hline(
    y=avg_merah,
    line_dash="dot",
    line_color="rgb(26, 118, 255)",
    annotation_text=f"Avg Merah = {avg_merah:.1f}",
    annotation_position="right",
    annotation_font=dict(color="rgb(26, 118, 255)")
)


# Layout
fig_line.update_layout(
    title='Weekly Trend',
    xaxis_title='Minggu',
    yaxis_title='Jumlah',
    plot_bgcolor='#fff',
    hovermode='x unified',
    legend=dict(orientation="h", y=1.2, x=1, xanchor="right")
)

st.plotly_chart(fig_line, use_container_width=True)


# ==== Doughnut Chart ====
with st.container():
    cols = st.columns([2, 3])

    total_merah = red_label_upper.loc[df_sampling.index].isin(['MERAH', 'TEXT']).sum()
    total_tidak_merah = total_data - total_merah

    pie_df = pd.DataFrame({
        'Label': ['Red Data', 'Not Red'],
        'Jumlah': [total_merah, total_tidak_merah]
    })

    fig_pie = px.pie(
        pie_df,
        names='Label',
        values='Jumlah',
        hole=0.5,
        title='Persentase',
        color='Label',
        color_discrete_map={
            'Red Data': 'red',
            'Not Red': "light blue"
        }
    )
    fig_pie.update_traces(
        textposition='inside',
        textinfo='label+percent+value',
        textfont = dict(color='white')
    )
    fig_pie.update_layout(
        showlegend=False,
        annotations=[dict(
            text=f"Total<br>{total_data:,}",
            x=0.5, y=0.5,
            font_size=16,
            showarrow=False
        )]
    )
    cols[0].plotly_chart(fig_pie, use_container_width=True)

    # ==== Daily Bar Chart: Jumlah Merah & Text (7 Hari Terakhir) ====
    # Pastikan kolom datetime benar
    if not pd.api.types.is_datetime64_any_dtype(df_sampling['Tanggal Sampling']):
        df_sampling['Tanggal Sampling'] = pd.to_datetime(df_sampling['Tanggal Sampling'])

    # Filter 7 hari terakhir
    last_7_days = df_sampling['Tanggal Sampling'].max() - pd.Timedelta(days=6)
    df_last7 = df_sampling[df_sampling['Tanggal Sampling'] >= last_7_days]

    # Pisahkan berdasarkan Red Label (use cached upper on the last-7-day subset)
    last7_upper = df_last7['Red Label'].str.upper()
    df_merah = df_last7[last7_upper == "MERAH"]
    df_text = df_last7[last7_upper == "TEXT"]

    # Hitung jumlah per hari
    df_merah_daily = df_merah.groupby('Tanggal Sampling').size().reset_index(name='MERAH')
    df_text_daily = df_text.groupby('Tanggal Sampling').size().reset_index(name='TEXT')

    # Gabungkan data
    df_bar = pd.merge(df_merah_daily, df_text_daily, on='Tanggal Sampling', how='outer').fillna(0)
    df_bar = df_bar.sort_values(by='Tanggal Sampling')

    # Ubah ke long format untuk stacked bar
    df_melted_bar = df_bar.melt(
        id_vars='Tanggal Sampling',
        value_vars=['MERAH', 'TEXT'],
        var_name='Label',
        value_name='Jumlah'
    )

    # Stacked Bar Chart
    fig_bar = px.bar(
        df_melted_bar,
        x='Tanggal Sampling',
        y='Jumlah',
        color='Label',
        title='Jumlah Sampling per Hari (7 Hari Terakhir)',
        text='Jumlah',
        color_discrete_map={
            'MERAH': '#dc3545',
            'TEXT': '#f4a261'
        }
    )
    fig_bar.update_layout(
        barmode='stack',
        xaxis_title=None,
        yaxis_title=None,
        plot_bgcolor="#fff",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.15, x=0, xanchor="left")
    )
    fig_bar.update_traces(
        textposition='inside'
    )

    cols[1].plotly_chart(fig_bar, use_container_width=True)


# Page 3
