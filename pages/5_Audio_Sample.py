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


# Cached data loader — avoids re-reading CSVs on every Streamlit re-render
@st.cache_data(ttl=3600)
def load_csv(path, **kwargs):
    """Load a CSV once and cache the result for 1 hour."""
    return pd.read_csv(path, **kwargs)


# Reusable AgGrid renderer — replaces 8 repeated blocks
def render_aggrid(df, height=400):
    """Build and display an AgGrid table with standard options."""
    gb = GridOptionsBuilder.from_dataframe(df)
    for col in df.columns:
        gb.configure_column(col, filter=False, sortable=True, resizable=True)
    gb.configure_pagination()
    AgGrid(df, gridOptions=gb.build(), height=height)

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
    

st.title('Voice Labelling')
df = load_csv('dataset_qc/sampling_hotline.csv')

# df.fillna('-', inplace=True
df['tanggal_sampling'] = pd.to_datetime(df['tanggal_sampling'], errors='coerce').dt.date
df['tanggal_meeting'] = pd.to_datetime(df['tanggal_meeting'], errors='coerce').dt.date

meeting_data = {}

for _, row in df.iterrows():
    tanggal_meeting = row['tanggal_meeting']
    if pd.isna(tanggal_meeting):
        continue
    checker = row['checker']
    agent = row['agent_sampling']

    # Ambil nama audio
    audio_filename = str(row.get('file_audio', '')).strip()
    if not audio_filename or audio_filename.lower() == 'nan':
        audio_file = None
    else:
        audio_file = f'audio/{audio_filename}'

    # nama file gambar
    screenshot_file_1 = build_screenshot_path(row.get('file_screenshot', ''))
    
    def safe_str(value):
        return '' if pd.isna(value) else str(value).strip()

    if not screenshot_file_1 and not audio_filename:
        continue

    entry = {
        'checker': checker,
        'agent': agent,
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
manual_order = ['Aulia', 'Neneng', 'Azer', 'Reza']
agent_list = [agent for agent in manual_order if agent in {entry['agent'] for entry in meeting_data[selected_date]}]
selected_agent = st.sidebar.radio('Agent Sampling', agent_list)

st.markdown(f"### {selected_agent}")

filtered_entries = [
    item for item in meeting_data[selected_date]
    if item['agent'] == selected_agent
]

for i in range(0, len(filtered_entries), 2):
    row_entries = filtered_entries[i:i+2]
    cols = st.columns(2)

    for j, item in enumerate(row_entries):
        idx = i + j + 1

        with cols[j]:
            with st.expander(f'Case {idx}', expanded=False):
                show_image(item.get('file_1'))
                if item['file_audio']:
                    try:
                        st.audio(item['file_audio'])
                    except Exception as e:
                        st.info('No Audio')