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
    


with st.container():
    cols = st.columns([3.5,0.5])

    with cols[0]:
        st.title("KULA Dashboard")
    with cols[1]:
        granularity = st.selectbox(
            '',
            options=['Daily', 'Weekly', 'Monthly'],
            index=0
        )

# Chart 1: Ratio Success Rate
df_ratio = load_csv('dataset_kula/success_ratio.csv')
df_ratio['Date'] = pd.to_datetime(df_ratio['Date'])

# Default range: 2 minggu terakhir
end_date = df_ratio['Date'].max()
start_date = end_date - timedelta(days=13)  # total 14 hari termasuk hari ini

# Tampilkan date range filter
selected_range = st.sidebar.date_input(
    "Select Date",
    value=(start_date, end_date),
    min_value=df_ratio['Date'].min(),
    max_value=df_ratio['Date'].max()
)

# Filter data berdasarkan tanggal
if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start, end = selected_range
    filtered_df = df_ratio[(df_ratio['Date'] >= pd.to_datetime(start)) & (df_ratio['Date'] <= pd.to_datetime(end))]
else:
    filtered_df = df_ratio.copy()

filtered_df = aggregation_ratio(filtered_df, 'Date', granularity)

# point on line
fig = px.line(
    filtered_df.sort_values('Date'),
    x='Date',
    y='Robot Success ratio',
    title='Ratio Success Rate 机器人有效拦截率',
    markers=True,
    text='Robot Success ratio'
)

fig.update_traces(
    textposition="top center",
    text=[f"<span style='color:black'>{x:.2f}%" for x in filtered_df['Robot Success ratio']],
    fill='tonexty',
    fillcolor='rgba(0, 123, 255, 0.2)'
)

y_min = filtered_df['Robot Success ratio'].min()
y_max = filtered_df['Robot Success ratio'].max()
x_min = filtered_df['Date'].min()
x_max = filtered_df['Date'].max()

y_margin = (y_max - y_min) * 0.25

fig.update_layout(
    xaxis_title='',
    xaxis=dict(range=[x_min - pd.Timedelta(days=1), x_max + pd.Timedelta(days=1)]),
    yaxis_title='',
    yaxis=dict(
        range=[y_min - y_margin, y_max + y_margin],
        ticksuffix='%'
    ),
    template='plotly_white'
)
 
st.plotly_chart(fig, use_container_width=True)


# Chart 2: CSAT Robot

csat_before = load_csv('dataset_kula/csat_before_takeout.csv')
csat_after = load_csv('dataset_kula/csat_after_takeout.csv')

# Parse dates
csat_before['Date'] = pd.to_datetime(csat_before['Date'], errors='coerce')
csat_after['Date'] = pd.to_datetime(csat_after['Date'], errors='coerce')

# filter by selected range
start_dt = pd.to_datetime(start)
end_dt = pd.to_datetime(end)
before_filtered = csat_before[(csat_before['Date'] >= start_dt) & (csat_before['Date'] <= end_dt)]
after_filtered = csat_after[(csat_after['Date'] >= start_dt) & (csat_after['Date'] <= end_dt)]

# Aggregate per granularity
filtered_df = aggregate_csat_dual(before_filtered, after_filtered, 'Date', granularity)

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=filtered_df['Date'],
    y=filtered_df['CSAT [Before]'],
    mode='lines+markers+text',
    name='Before take out',
    text=[f"<span style='color:black'>{x:.2f}" for x in filtered_df['CSAT [Before]']],
    textposition='top center',
    fill='tonexty',
    fillcolor='rgba(0, 123, 255, 0.2)'
))

fig.add_trace(go.Scatter(
    x=filtered_df['Date'],
    y=filtered_df['CSAT [After]'],
    mode='lines+markers+text',
    name='After take out',
    line=dict(color='red'),
    text=[f"<span style='color:black'>{x:.2f}" for x in filtered_df['CSAT [After]']],
    textposition='top center',
    fill='tonexty',
    fillcolor='rgba(255,0,0,0.2)'
))

if not filtered_df.empty:
    x_min = filtered_df['Date'].min()
    x_max = filtered_df['Date'].max()
else:
    # fallback
    x_min, x_max = start_dt, end_dt

fig.update_layout(
    title='CSAT Robot 机器人用户满意度',
    xaxis=dict(range=[(x_min - pd.Timedelta(days=1)),x_max + pd.Timedelta(days=1)]),
    yaxis_title='',
    yaxis=dict(range=[1,5]),
    legend=dict(
        orientation='v',
        yanchor='top',
        y=1.1,
        xanchor='right',
        x=1,
        title=None
    )
)

st.plotly_chart(fig, use_container_width=True)

# Load data bad survey
df_bad_survey = load_csv('dataset_kula/bad_survey.csv')

# Pastikan kolom tanggal dalam format datetime
df_bad_survey['Conversation Start Time'] = pd.to_datetime(df_bad_survey['Conversation Start Time'], errors='coerce')

# Sidebar filter untuk Company
company_filter, date_mode, selected_date = sidebar_filters()

if date_mode == 'Range':
    selected_range = (start, end)
else:
    selected_range = None

# Filter tanggal
if date_mode == 'Single' and selected_date:
    df_bad_survey = df_bad_survey[df_bad_survey['Conversation Start Time'].dt.date == selected_date]
elif date_mode == 'Range' and selected_range and len(selected_range) == 2:
    start_date, end_date = pd.to_datetime(selected_range[0]), pd.to_datetime(selected_range[1])
    df_bad_survey = df_bad_survey[df_bad_survey['Conversation Start Time'].between(start_date, end_date)]

# Terapkan filter company
if company_filter:
    df_bad_survey = df_bad_survey[df_bad_survey['Business Type'].isin(company_filter)]

# === Table 1: Sub Category with Granularity ===
if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
    subcat_summary = aggregate_table_with_granularity(
        df_bad_survey,
        category_col='Sub Category',
        date_col='Conversation Start Time',
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
else:
    subcat_summary = (
        df_bad_survey.groupby('Sub Category')
        .size()
        .reset_index(name='Total Sample')
        .sort_values('Total Sample', ascending=False)
    )

# === Table 2: QC result with Granularity ===
if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
    cat_summary = aggregate_table_with_granularity(
        df_bad_survey,
        category_col='QC Result',
        date_col='Conversation Start Time',
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
else:
    cat_summary = (
        df_bad_survey.groupby('QC Result')
        .size()
        .reset_index(name='Total Sample')
        .sort_values('Total Sample', ascending=False)
    )

# if there is percent label
if 'Total Sample' in subcat_summary.columns:
    subcat_summary['Percentage'] = (
        subcat_summary['Total Sample'] / subcat_summary['Total Sample'].sum() * 100
    ).round(2).astype(str) + '%'

if 'Total Sample' in cat_summary.columns:
    cat_summary['Percentage'] = (
        cat_summary['Total Sample'] / cat_summary['Total Sample'].sum() * 100
    ).round(2).astype(str) + '%'

# Tampilkan di dashboard AGGrid
with st.container():
    st.markdown("##### Bad Survey")
    cols = st.columns([0.5, 0.45])

    with cols[0]:
        render_aggrid(subcat_summary, height=300)

    with cols[1]:
        render_aggrid(cat_summary, height=300)

# Like and Dislike
st.markdown('##### Like and Dislike')
with st.container():
    cols = st.columns([1,4])
    
    #The Linechart
    df_like_dislike = load_csv('dataset_kula/kula_like_dislike.csv')
    df_like_dislike['Date'] = pd.to_datetime(df_like_dislike['Date'])

    df_like_dislike = df_like_dislike[(df_like_dislike['Date'] >= pd.to_datetime(start)) & (df_like_dislike['Date'] <= pd.to_datetime(end))]

    # Filter company
    if company_filter:
        df_like_dislike = df_like_dislike[
            df_like_dislike['Manual Check [business]'].isin(company_filter)
        ]

    df_daily = aggregate_sum(df_like_dislike, 'Date', granularity,{
        "solved_num": "sum",
        "unsolved_num": "sum"
    })
    df_daily.rename(columns={'solved_num': 'Like', 'unsolved_num': 'Dislike'}, inplace=True)

    latest_date = df_daily['Date'].max()
    latest_data = df_daily[df_daily['Date'] == latest_date].melt(
        id_vars='Date',
        value_vars=['Like', 'Dislike'],
        var_name='Category',
        value_name='Total'
    )

    # Bar chart
    bar_fig = px.bar(
        latest_data,
        x='Category',
        y='Total',
        color='Category',
        color_discrete_map={'Like': 'light blue','Dislike': 'red'},
        text='Total'
    )

    bar_fig.update_traces(textposition='inside')
    bar_fig.update_layout(
        yaxis_title='Jumlah',
        xaxis_title=None,
        showlegend=False,
        template='plotly_white'
    )

    # Tampilkan di kolom kiri
    cols[0].plotly_chart(bar_fig, use_container_width=True)


    # Plot line chart
    fig = go.Figure()

    # Like
    fig.add_trace(go.Scatter(
        x=df_daily['Date'],
        y=df_daily['Like'],
        mode='lines+markers+text',
        name='Like',
        text=[f"<span style='color:black'>{x}" for x in df_daily['Like']],
        textposition='top center',
        fill='tonexty',
        fillcolor='rgba(0, 123, 255, 0.2)'
    ))

    # Dislike
    fig.add_trace(go.Scatter(
        x=df_daily['Date'],
        y=df_daily['Dislike'],
        mode='lines+markers+text',
        name='Dislike',
        line=dict(color='red'),
        text=[f"<span style='color:black'>{x}" for x in df_daily['Dislike']],
        textposition='top center',
        fill='tonexty',
        fillcolor='rgba(255,0,0,0.2)'
    ))

    x_min = df_like_dislike['Date'].min()
    x_max = df_like_dislike['Date'].max()

    fig.update_layout(
        xaxis=dict(range=[x_min - pd.Timedelta(days=0.5), x_max + pd.Timedelta(days=0.5)]),
        yaxis=dict(title=None),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.1,
            xanchor="right",
            x=1
        )
    )

    cols[1].plotly_chart(fig, use_container_width=True)

# Tabel data category like and dislike
df_like_dislike['unsolved_num'] = pd.to_numeric(df_like_dislike['unsolved_num'], errors='coerce').fillna(0)

# Filter data berdasarkan date range & company jika perlu
if date_mode == 'Single' and selected_date:
    df_like_dislike = df_like_dislike[df_like_dislike['Date'].dt.date == selected_date]
elif date_mode == 'Range' and selected_range and len(selected_range) == 2:
    df_like_dislike = df_like_dislike[df_like_dislike['Date'].between(start_date, end_date)]

if company_filter:  # multiselect
    df_like_dislike = df_like_dislike[df_like_dislike['Manual Check [business]'].isin(company_filter)]

# ===== Table 1: Berdasarkan Team/Category =====
if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
    team_summary = aggregate_table_with_granularity(
        df_like_dislike,
        category_col = 'Team/Category',
        value_col = 'unsolved_num',
        date_col = 'Date',
        granularity = granularity,
        start_date = start_date,
        end_date = end_date
    )
else:
    team_summary = (
        df_like_dislike.groupby('Team/Category')
        .agg(
            **{
                'Total Dislike': ('unsolved_num', 'sum')
            }
        )
        .reset_index()
        .sort_values('Total Dislike', ascending=False)
    )

# ===== Table 2: Berdasarkan Background detail =====
if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
    bg_summary = aggregate_table_with_granularity(
        df_like_dislike,
        category_col='Background detail',
        value_col='unsolved_num',
        date_col='Date',
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
else:
    bg_summary = (
        df_like_dislike.groupby('Background detail')
        .agg(
            **{
                'Total Dislike': ('unsolved_num', 'sum')
            }
        )
        .reset_index()
        .sort_values('Total Dislike', ascending=False)
    )

# ===== Tampilkan di dashboard =====
st.markdown("##### Dislike Summary")
with st.container():
    cols = st.columns([0.45, 0.5])

    with cols[0]:
        render_aggrid(team_summary)

    with cols[1]:
        render_aggrid(bg_summary)


    # Table QC KULA
    df_qc_kula = load_csv('dataset_kula/qc_kula.csv')
    df_qc_kula['Score_date'] = pd.to_datetime(df_qc_kula['Score_date'], errors='coerce')

    if date_mode == 'Single' and selected_date:
        df_qc_kula = df_qc_kula[df_qc_kula['Score_date'].dt.date == selected_date]
    elif date_mode == 'Range' and selected_range and len(selected_range) == 2:
        start_date, end_date = pd.to_datetime(selected_range[0]), pd.to_datetime(selected_range[1])
        df_qc_kula = df_qc_kula[df_qc_kula['Score_date'].between(start_date, end_date)]

    # Filter the company
    if company_filter:
        df_qc_kula = df_qc_kula[df_qc_kula['Business Type'].isin(company_filter)]

    # === Table 1: Main Category & Sub Category ===
    if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
        main_sub_summary = aggregate_table_with_granularity(
            df_qc_kula,
            category_col=['Main Category', 'Checking Result (Sub Category)'],
            date_col='Score_date',
            granularity=granularity,
            start_date=start_date,
            end_date=end_date
        )
    else:
        main_sub_summary = (
            df_qc_kula.groupby(['Main Category', 'Checking Result (Sub Category)'])
            .size()
            .reset_index(name='Total Sample')
            .sort_values('Total Sample', ascending=False)
        )

    # === Table 2: Team Category ===
    if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
        team_cat_qc = aggregate_table_with_granularity(
            df_qc_kula,
            category_col='Team/Category',
            date_col='Score_date',
            granularity=granularity,
            start_date=start_date,
            end_date=end_date
        )
    else:
        team_cat_qc = (
            df_qc_kula.groupby('Team/Category')
            .size()
            .reset_index(name='Total Sample')
            .sort_values('Total Sample', ascending=False)
        )

    # === Table 3: Background Detail ===
    if granularity in ['Weekly', 'Monthly'] and date_mode == 'Range':
        bg_summary = aggregate_table_with_granularity(
            df_qc_kula,
            category_col='Background detail- ID',
            date_col='Score_date',
            granularity=granularity,
            start_date=start_date,
            end_date=end_date
        )
    else:
        bg_summary = (
            df_qc_kula.groupby('Background detail- ID')
            .size()
            .reset_index(name='Total Sample')
            .sort_values('Total Sample', ascending=False)
        )

    # === Show the data ===
    st.markdown('##### QC Dislike')
    with st.container():
        cols = st.columns([4, 3])

        with cols[0]:
            render_aggrid(main_sub_summary)

        with cols[1]:
            render_aggrid(team_cat_qc)
    
    with st.container():
        cols = st.columns([3,2])

        with cols[0]:
            render_aggrid(bg_summary)
