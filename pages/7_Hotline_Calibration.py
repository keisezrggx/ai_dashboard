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
    

st.title('Hotline Calibration')
df = load_csv('dataset_qc/sampling_hotline.csv')

# df.fillna('-', inplace=True
df['tanggal_sampling'] = pd.to_datetime(df['tanggal_sampling'], errors='coerce').dt.date
df['tanggal_meeting'] = pd.to_datetime(df['tanggal_meeting'], errors='coerce').dt.date

meeting_data = {}

for _, row in df.iterrows():
    tanggal_meeting = row['tanggal_meeting']
    checker = row['checker']
    agent = row['agent_sampling']

    # Ambil nama audio
    audio_filename = str(row.get('file_audio', '')).strip()
    audio_file = f'audio/{audio_filename}' if audio_filename else None

    # nama file gambar
    screenshot_file_1 = build_screenshot_path(row.get('file_screenshot', ''))

    # teks recheck
    sections = []
    
    mapping = [
        # static data
        {
            'type': 'static',
            'col': 'asi/afi',
            'label': 'Comp'
        },

        {
            'type': 'static',
            'col': 'call_id',
            'label': 'Call ID'
        },

        {
            'type': 'static',
            'col': 'detik',
            'label': 'Detik'
        },

        {
            'type': 'static',
            'col': 'alasan',
            'label': 'Alasan'
        },

        #dynamic data
        {
            'type': 'compare',
            'final': 'hasil_pemeriksaan_kualitas_ubah',
            'text_awal': 'hasil_pemeriksaan_kualitas',
            'label': 'Hasil Pemeriksaan Kualitas'
        },
        
        {
            'type': 'compare',
            'final': 'efektif_ubah',
            'text_awal': 'efektif',
            'label': 'Efektif'
        },
        
        {
            'type': 'compare',
            'final': 'kejelasan_suara_ubah',
            'text_awal': 'kejelasan_suara',
            'label': 'Kejelasan Suara'
        },

        {
            'type': 'compare',
            'final': 'suara_lain_ubah',
            'text_awal': 'suara_lain',
            'label': 'Suara Lain'
        },

        {
            'type': 'compare',
            'final': 'kelengkapan_rekaman_ubah',
            'text_awal': 'kelengkapan_rekaman',
            'label': 'Kelengkapan Rekaman'
        }
    ]
    
    asi_afi = str(row.get("asi/afi", "")).strip()
    call_id = str(row.get('call_id', '')).strip()
    detik = str(row.get('detik', '')).strip()
    alasan = str(row.get('alasan', '')).strip()
    kelengkapan_rekaman = str(row.get('kelengkapan_rekaman', '')).strip()

    if asi_afi or call_id:
        sections.append(
            f'**Comp:** {asi_afi}  \n'
            f'**Call ID:** {call_id}  \n'
            f'**Detik:** {detik}  \n'
        )

    for item in mapping:
        if item['type'] == 'compare':

            text_awal = str(row.get(item['text_awal'], '')).strip()
            hasil = str(row.get(item['final'], '')).strip()

            if text_awal:
                sections.append(
                    f'**{item['label']}:** {text_awal}  \n'
                    f'**Diubah:** {hasil}   \n'
                )

    if alasan:
        sections.append(f'**Text Sebelum:** {alasan}  \n')
            
    if not sections and not screenshot_file_1 and not audio_filename:
        continue

    entry = {
        'checker': checker,
        'agent': agent,
        'text': f'**Checker:** {checker}' + ('\n\n' + '\n'.join(sections) if sections else ''),
        'file_1': screenshot_file_1,
        'file_audio': audio_file
    }

    if tanggal_meeting not in meeting_data:
        meeting_data[tanggal_meeting] = []

    meeting_data[tanggal_meeting].append(entry)

dates = sorted(meeting_data.keys())

if not dates:
    st.warning('Tidak ada data meeting.')
    st.stop()

#Sidebar tanggal meeting
selected_date = st.sidebar.date_input(
    'Tanggal Meeting',
    value=max(meeting_data.keys()),
    min_value=min(meeting_data.keys()),
    max_value=max(meeting_data.keys())
)

if selected_date not in meeting_data:
    st.warning(f'Tidak ada data untuk tanggal {selected_date.strftime("%d %B %Y")}')
    st.stop()

# Date filter
manual_order = ['Azer', 'Aulia', 'Neneng', 'Reza']
agent_list = [agent for agent in manual_order if agent in {entry['agent'] for entry in meeting_data[selected_date]}]
selected_agent = st.sidebar.radio('Agent Sampling', agent_list)

st.markdown(f"### {selected_agent}")

filtered_entries = [
    item for item in meeting_data[selected_date]
    if item['agent'] == selected_agent
]

for i in range(0, len(filtered_entries), 3):
    row_entries = filtered_entries[i:i+3]
    cols = st.columns(len(row_entries))

    for idx, item in enumerate(filtered_entries, start=1):
        
        head_case, head_s = st.columns([0.8, 1.2])

        with head_case:
            with st.expander(f'Case {idx}', expanded=False):
                st.markdown(item['text'], unsafe_allow_html=True)
                if item['file_audio']:
                    try:
                        st.audio(item['file_audio'])
                    except Exception as e:
                        st.info('No Audio')

        with head_s:
            with st.expander(f'Screenshot {idx} - 1', expanded=False):
                show_image(item.get('file_1'))
