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
    

df_sampling = load_csv(
    'dataset_qc/kalib_sampling.csv',
    parse_dates=['Tanggal Sampling']
)

# Filter
df_sampling = df_sampling[df_sampling['Agent Sampling'] != 'No Data']
validators = [name for name in df_sampling['Agent Sampling'].unique() if name != "Irman"]
validator = st.sidebar.radio('Validators', validators)

# Custom CSS for card style
st.markdown("""
    <style>
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0px 2px 10px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    .card p {
        margin: 0;
        font-size: 14px;
        color: gray;
    }
    </style>
""", unsafe_allow_html=True)

# Accuracy Data
acc_df = calculate_checker_accuracy(df_sampling)
acc_row = acc_df[acc_df["Checker"] == validator]

total_tagging = acc_row["Total_Tagging"].values[0] if not acc_row.empty else 0
kesalahan = acc_row["Kesalahan"].values[0] if not acc_row.empty else 0
acc_value = acc_row["Accuracy"].values[0] if not acc_row.empty else None

benar = total_tagging - kesalahan if total_tagging > 0 else 0

# Layout
cols = st.columns([2, 3, 3, 4])

# Image column
with cols[0]:
    images = {
        "Aulia": "pict/aul.png",
        "Reza": "pict/reza.png",
        "Neneng": "pict/neneng.png",
        "Azer": "pict/azer.png"
        # Add other mappings if needed
    }
    if validator in images:
        st.image(images[validator], width=200)

# Info card
with cols[1]:
    st.markdown(f"""
        <div class="card", style="text-align: left;">
            <h3>{validator}</h3>
            <p>Quality Control Specialist</p>
            <br>
        </div>
    """, unsafe_allow_html=True)

# Accuracy card
with cols[2]:
    if acc_value is not None:
        st.markdown(f"""
            <div class="card" style="
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                padding: 20px;
            ">
                <h5>Accuracy</h5>
                <h3>{acc_value:.2f}%</h3>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="card" style="
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                padding: 20px;
            ">
                <h6>Accuracy</h6>
                <h3>-</h3>
                <p>No data</p>
            </div>
        """, unsafe_allow_html=True)


# Tag Count card
with cols[3]:
    if total_tagging > 0:
        pie_data = {
            "Category": ["Benar", "Salah"],
            "Count": [benar, kesalahan]
        }
        fig = px.pie(
            pie_data,
            values="Count",
            names="Category",
            color="Category",
            color_discrete_map={"Salah": "#5fa8d3", "Benar": "#1b4965"},
            hole=0.65,
            title='Tag Count'
        )
        fig.update_traces(
            textposition='inside',
            textinfo='value',
            pull=[0.05]*len([pie_data]),
            marker=dict(line=dict(color='white', width=2)),
            insidetextorientation='horizontal'
        )
        fig.update_layout(
            showlegend=False,
            title=dict(
                x=0.5,
                xanchor='center',
                yanchor='top'
            ),
            margin=dict(t=40, b=20, l=20, r=20),
            height=240,
            annotations=[dict(
                text="{}<br>Tagged".format(total_tagging),
                font_size=14,
                showarrow=False,
                xanchor="center"
            )],
        )

        # Masukkan ke card container
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("""
            <div class="card">
                <h6>Tagging Result</h6>
                <p>No data</p>
            </div>
        """, unsafe_allow_html=True)

# radar chart
cols = st.columns([3,5])
with cols[0]:
    df_checker, count_cols = aggregate_checker_errors(df_sampling)

    row = df_checker[df_checker["Checker"] == validator].iloc[0]

    r = row[count_cols].values.tolist()
    theta = count_cols

    theta_clean = [t.replace("Count ", "") for t in theta]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=r + [r[0]],
            theta=theta_clean + [theta_clean[0]], 
            fill='toself',
            name=validator,
            line=dict(color='crimson')
        )
    )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max(r)+2])),
        showlegend=False,
        width=300,
        height=300,
        margin=dict(l=30, r=30, t=2, b=30)
    )

    st.plotly_chart(fig, use_container_width=True)

# Barchart mistake per week
with cols[1]:
    # Pastikan kolom datetime benar
    if not pd.api.types.is_datetime64_any_dtype(df_sampling['Tanggal Sampling']):
        df_sampling['Tanggal Sampling'] = pd.to_datetime(df_sampling['Tanggal Sampling'])

    # Ambil bulan & tahun unik dari data
    available_months = df_sampling['Tanggal Sampling'].dt.to_period('M').unique()
    available_months = sorted(available_months)

    # Konversi ke format label misalnya "Oktober 2025"
    month_labels = [p.strftime("%B %Y") for p in available_months]

    # Sidebar pilih bulan
    selected_month_label = st.sidebar.selectbox("Pilih Bulan", month_labels)
    selected_period = available_months[month_labels.index(selected_month_label)]

    # Filter data sesuai bulan & tahun yang dipilih
    df_current = df_sampling[(df_sampling['Tanggal Sampling'].dt.month == selected_period.month) &
                             (df_sampling['Tanggal Sampling'].dt.year == selected_period.year)]

    # Tambahkan kolom week
    df_current['week'] = df_current['Tanggal Sampling'].apply(week_of_month)

    # Hitung minggu maksimal yang bisa dipilih
    if (selected_period.month == datetime.now().month) and (selected_period.year == datetime.now().year):
        current_week = week_of_month(datetime.now())
    else:
        current_week = df_current['week'].max()

    week_labels = [f"week {i}" for i in range(1, current_week + 1)]

    # Sidebar filter untuk minggu
    week1_label = st.sidebar.selectbox('First Chart', week_labels)
    week2_label = st.sidebar.selectbox('Second Chart', week_labels)

    week1_num = int(week1_label.split()[-1])
    week2_num = int(week2_label.split()[-1])

    # Filter data sesuai validator & minggu
    df_week1 = df_current[(df_current['Checker'] == validator) & 
                        (df_current['week'] == week1_num)]

    df_week2 = df_current[(df_current['Checker'] == validator) & 
                        (df_current['week'] == week2_num)]

    # Variabel yang dipakai
    variables = ['Count Kejelasan Suara', 'Count Efektif', 'Count Hasil Pemeriksaan Kualitas',
                'Count Hasil ASR', 'Count Revisi Text', 'Count Kelengkapan Rekaman']

    week1_counts = [df_week1[var].sum() for var in variables]
    week2_counts = [df_week2[var].sum() for var in variables]

    # Bersihkan nama variabel (hapus "Count ")
    clean_labels = [v.replace("Count ", "") for v in variables]

    # Plot horizontal bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=clean_labels,
        x=week2_counts,
        name=week2_label,
        marker_color='crimson',
        orientation='h',
        text=week2_counts,
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        y=clean_labels,
        x=week1_counts,
        name=week1_label,
        marker_color='lightslategrey',
        orientation='h',
        text=week1_counts,
        textposition='outside'
    ))

    fig.update_layout(
        barmode='group',
        xaxis_title='Jumlah Kesalahan',
        yaxis_title='Kategori Kesalahan',
        template='plotly_white',
        height=400,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=True, gridcolor='lightgrey', gridwidth=0.5),
        yaxis=dict(showgrid=True, gridcolor='lightgrey', gridwidth=0.5)

    )

    st.plotly_chart(fig, use_container_width=True)


# Page 6
