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
    

def styled_metric(label, value, delta, delta_color="normal"):
    delta_symbol = "↑" if delta_color == "normal" else ("↓" if delta_color == "inverse" else "")
    delta_color_code = {
        "normal": "#28a745",     # hijau
        "inverse": "#dc3545",    # merah
        "off": "#999999"         # abu netral
    }.get(delta_color, "#000000")

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
            <div style="font-size: 14px; font-weight: bold; color: {delta_color_code};">{delta_symbol} {delta:,}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# Dashboard
df = load_csv('dataset_qc/new_4_clean.csv', parse_dates=['Tanggal Pengerjaan', 'Waktu Inbound'])

# Filter "Tidak bisa di Play"
df_filtered = df[df['Efektif'] != 'Tidak bisa di Play']

# Sidebar Filters
asi_afi_filter = st.sidebar.selectbox("ASI/AFI", ['All'] + df['ASI/AFI'].unique().tolist())
checker_filter = st.sidebar.selectbox("Checker", ['All'] + df['Checker'].unique().tolist())
date_range = st.sidebar.date_input("Tanggal Pengerjaan", [df['Tanggal Pengerjaan'].min(), df['Tanggal Pengerjaan'].max()])

# Apply Filters
mask = (
    (df['Tanggal Pengerjaan'].dt.date >= date_range[0]) &
    (df['Tanggal Pengerjaan'].dt.date <= date_range[1])
)
if asi_afi_filter != 'All':
    mask &= (df['ASI/AFI'] == asi_afi_filter)
if checker_filter != 'All':
    mask &= (df['Checker'] == checker_filter)

df_filtered = df_filtered[mask]

# Score Cards
with st.container():
    st.title("AI - Quality Control Dashboard")
    
    latest_date = df["Tanggal Pengerjaan"].max()
    latest_date_str = latest_date.strftime("%d/%m/%Y")

    st.markdown(f"##### Hotline - updated till {latest_date_str}")


    cols = st.columns(5)

    # Compute date masks ONCE, then use value_counts for O(1) lookups
    last_selected_date = date_range[1]
    day_before_last = last_selected_date - pd.Timedelta(days=1)
    date_col = df['Tanggal Pengerjaan'].dt.date

    mask_until = (date_col >= date_range[0]) & (date_col <= last_selected_date)
    mask_before = (date_col >= date_range[0]) & (date_col <= day_before_last)

    count_until_last = mask_until.sum()
    count_before = mask_before.sum()

    delta_tagged = count_until_last - count_before
    if delta_tagged > 0:
        delta_color_tagged = "normal"
    elif delta_tagged < 0:
        delta_color_tagged = "inverse"
    else:
        delta_color_tagged = "off"
    with cols[0]:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        styled_metric("Total Tagged", f"{count_until_last:,}", delta_tagged, delta_color_tagged)
        st.markdown('</div>', unsafe_allow_html=True)

    # Efektif Score Cards — use value_counts instead of N separate full-DataFrame scans
    efektif_list = ['On Target/HC', 'On Target/Not HC', 'Miss Target/ Not HC', 'Miss Target/HC']
    counts_until = df.loc[mask_until, 'Efektif'].value_counts()
    counts_before = df.loc[mask_before, 'Efektif'].value_counts()

    for i, label in enumerate(efektif_list):
        cnt_until = counts_until.get(label, 0)
        cnt_before = counts_before.get(label, 0)

        delta = cnt_until - cnt_before
        if delta > 0:
            delta_color = "normal"
        elif delta < 0:
            delta_color = "inverse"
        else:
            delta_color = "off"
        with cols[i + 1]:
            st.markdown('<div class="metric-box">', unsafe_allow_html=True)
            styled_metric(label, f"{cnt_until:,}", delta, delta_color)
            st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    "<h5 style='text-align: center;'>Current AI Accuracy: 95.43%</h5>",
    unsafe_allow_html=True
    )

# Line Chart Graphic
with st.container():

    df_weekly = df_filtered.copy()
    df_weekly['Week'] = df_weekly['Tanggal Pengerjaan'].dt.to_period('W').dt.start_time

    # Grafik 1: Hanya kategori "Miss Target/ Not HC"
    df_miss_target_not_hc = df_weekly[df_weekly['Efektif'] == 'Miss Target/ Not HC']
    df_miss_group = df_miss_target_not_hc.groupby(['Week', 'Efektif']).size().reset_index(name='Count')

    # Urutkan Week dan ambil 2 minggu terakhir
    df_miss_group = df_miss_group.sort_values('Week')
    unique_weeks = df_miss_group['Week'].drop_duplicates().sort_values()
    last_2_weeks = unique_weeks.iloc[-1:].tolist()

    # Plot
    fig_miss = px.line(
        df_miss_group,
        x='Week',
        y='Count',
        color='Efektif',
        title='Weekly Trend: Miss Target/Not HC',
        text='Count'
    )
    fig_miss.update_traces(
        mode='lines+markers+text',
        textposition='top center',
        textfont=dict(size=12, color='black')
    )
    fig_miss.update_layout(
        yaxis=dict(title=None),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.1,
            xanchor="right",
            x=1
        )
    )
    st.plotly_chart(fig_miss, use_container_width=True)

    # Grafik 2: 3 kategori lainnya
    other_labels = ['Miss Target/HC', 'On Target/Not HC', 'On Target/HC']
    df_others = df_weekly[df_weekly['Efektif'].isin(other_labels)]
    df_others_group = df_others.groupby(['Week', 'Efektif']).size().reset_index(name='Count')
    fig_others = px.line(
        df_others_group,
        x='Week',
        y='Count',
        color='Efektif',
        title='Weekly Trends: Other Categories',
        text='Count'
    )
    fig_others.update_traces(
        mode='lines+markers+text',
        textposition = 'top center',
        textfont=dict(size=12, color='black')
    )
    fig_others.update_layout(
        yaxis=dict(title=None),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.1,
            xanchor="left",
            x=0.5
        )
    )
    st.plotly_chart(fig_others, use_container_width=True)
    
with st.container():
    cols = st.columns(2)

    # Checker Doughnut Graph
    asr_result = df_filtered['Hasil ASR'].value_counts().reset_index()
    asr_result.columns = ['Kategori', 'Jumlah']
    total_asr = "{:,}".format(asr_result['Jumlah'].sum())

    # Doughnut Chart dengan label di luar dan garis penunjuk
    fig_asr = px.pie(
        asr_result,
        values='Jumlah',
        names='Kategori',
        hole=0.5,
        title='Hasil ASR',
        color='Kategori',
        color_discrete_map={
            'Terdapat kesalahan': 'red',
            'No Data': 'gray',
            'Entri Akurat': 'light blue'
        }
    )

    fig_asr.update_traces(
        textposition='inside',  # Label di luar chart
        textinfo='label+percent',
        pull=[0.05]*len(asr_result),
        marker=dict(line=dict(color='white', width=2))
    )

    fig_asr.update_layout(
        showlegend=False,  # Set True jika ingin daftar legend di samping
        annotations=[dict(
            text=f"Total<br>{total_asr}",
            x=0.5,
            y=0.5,
            font_size=16,
            showarrow=False
        )]
    )

    cols[0].plotly_chart(fig_asr, use_container_width=True)

    # ASI/AFI Bar Graph di kolom kedua
    asi_afi_count = df_filtered['ASI/AFI'].value_counts().reset_index()
    asi_afi_count.columns = ['ASI/AFI', 'Count']
    
    asi_afi_count['Percent'] = asi_afi_count['Count'] / asi_afi_count['Count'].sum() * 100
    asi_afi_count['Label'] = asi_afi_count.apply(lambda row: f"{row['Count']:,} Tag<br>({row['Percent']:.1f}%)", axis=1)

    fig_asi_afi = px.bar(
        asi_afi_count,
        x='ASI/AFI',
        y='Count',
        color='ASI/AFI',
        title='ASI vs AFI',
        text='Label',
        color_discrete_map={'ASI': '#1f77b4', 'AFI': 'RED'}
    )

    fig_asi_afi.update_traces(
        textposition='inside'
    )
    fig_asi_afi.update_layout(showlegend=False)

    cols[1].plotly_chart(fig_asi_afi, use_container_width=True)

with st.container():
    cols = st.columns([1, 1])

    checker_count = df_filtered['Checker'].value_counts().reset_index()
    checker_count.columns = ['Checker', 'Count']
    total_checker = "{:,}".format(checker_count['Count'].sum())
    fig_checker = px.pie(
        checker_count,
        values='Count',
        names='Checker',
        hole=0.5,
        title='Checker Distribution'
    )
    fig_checker.update_traces(
        textposition='inside',
        textinfo='label+percent+value'
    )
    fig_checker.update_layout(
        showlegend=False,
        annotations=[dict(
            text=f"Total<br>{total_checker}",
            x=0.5,
            y=0.5,
            font_size=16,
            
            showarrow=False
        )]
    )
    cols[0].plotly_chart(fig_checker, use_container_width=True)


#Page 2
