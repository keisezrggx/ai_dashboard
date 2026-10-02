from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / 'dataset_qc' / 'sampling_hotline.csv'
MEDIA_FIELDS = (
    ('hasil_pemeriksaan_kualitas', 'hasil_pemeriksaan_kualitas_ubah', 'Hasil Pemeriksaan Kualitas'),
    ('efektif', 'efektif_ubah', 'Efektif'),
    ('kejelasan_suara', 'kejelasan_suara_ubah', 'Kejelasan Suara'),
    ('suara_lain', 'suara_lain_ubah', 'Suara Lain'),
    ('kelengkapan_rekaman', 'kelengkapan_rekaman_ubah', 'Kelengkapan Rekaman'),
)
AGENT_ORDER = ('Azer', 'Neneng', 'Aulia', 'Reza')

st.set_page_config(layout='wide')
st.title('Hotline Calibration')


@st.cache_data(ttl=3600)
def load_meetings(path: Path, modified_at: int) -> pd.DataFrame:
    data = pd.read_csv(path)
    data['tanggal_meeting'] = pd.to_datetime(data['tanggal_meeting'], errors='coerce').dt.date
    return data.dropna(subset=['tanggal_meeting'])


def text(value: object) -> str:
    return '' if pd.isna(value) else str(value).strip()


def media_path(directory: str, filename: object) -> Path | None:
    name = text(filename)
    if not name or name == '-':
        return None
    return ROOT / directory / name


def case_rows(row: pd.Series) -> list[tuple[str, str]]:
    rows = []
    for column, label in (('asi/afi', 'Company'), ('call_id', 'Call ID'), ('detik', 'Detik')):
        value = text(row.get(column, ''))
        if value:
            rows.append((label, value))
    if rows:
        rows.append(('', ''))

    for original, revised, label in MEDIA_FIELDS:
        value = text(row.get(original, ''))
        if value:
            rows.append((label, value))
            updated = text(row.get(revised, ''))
            if updated:
                rows.append(('Diubah', updated))
            rows.append(('', ''))

    reason = text(row.get('alasan', ''))
    if reason:
        rows.append(('Alasan', reason))
    return rows


def render_case(row: pd.Series, index: int) -> None:
    rows = case_rows(row)
    screenshot = media_path('screenshots', row.get('file_screenshot', ''))
    audio = media_path('audio', row.get('file_audio', ''))
    if not rows and screenshot is None and audio is None:
        return

    details, image = st.columns([0.8, 1.2])
    with details:
        st.markdown(f'**Checker:** {text(row.get("checker", ""))}')
        table_rows = ''.join(
            '<tr><td style="padding: 6px 8px; vertical-align: top; width: 180px; font-weight: 600; color: #111;">'
            f'{escape(label)}</td><td style="padding: 6px 8px; vertical-align: top; color: #111;">'
            f'{escape(value)}</td></tr>'
            for label, value in rows
        )
        st.markdown(
            '<table style="border-collapse: collapse; width: 100%; margin-bottom: 1rem;">'
            f'{table_rows}</table>',
            unsafe_allow_html=True,
        )
        if audio is not None:
            if audio.is_file():
                st.audio(str(audio))
            else:
                st.info('No Audio')

    with image:
        if screenshot is None:
            st.error('Image Restricted.')
        elif screenshot.is_file():
            st.image(str(screenshot))
        else:
            st.info('No image.')


def move_case(step: int, count: int) -> None:
    st.session_state.hotline_case_index = max(
        0, min(st.session_state.hotline_case_index + step, count - 1)
    )


try:
    meetings = load_meetings(DATA_PATH, DATA_PATH.stat().st_mtime_ns)
except (OSError, pd.errors.ParserError, KeyError) as exc:
    st.error(f'Cannot load meeting data: {exc}')
    st.stop()

if meetings.empty:
    st.warning('Tidak ada data meeting.')
    st.stop()

available_dates = sorted(meetings['tanggal_meeting'].unique())
selected_date = st.sidebar.date_input(
    'Tanggal Meeting',
    value=available_dates[-1],
    min_value=available_dates[0],
    max_value=available_dates[-1],
)

selected_meetings = meetings.loc[meetings['tanggal_meeting'] == selected_date]
if selected_meetings.empty:
    st.warning(f'Tidak ada data untuk tanggal {selected_date.strftime("%d %B %Y")}')
    st.stop()

agents = set(selected_meetings['agent_sampling'].dropna())
agent_list = [agent for agent in AGENT_ORDER if agent in agents]
if not agent_list:
    st.warning('Tidak ada agent sampling untuk tanggal ini.')
    st.stop()

selected_agent = st.radio('Agent Sampling', agent_list, horizontal=True)
agent_meetings = selected_meetings.loc[selected_meetings['agent_sampling'] == selected_agent]
cases = [
    row for _, row in agent_meetings.iterrows()
    if case_rows(row)
    or media_path('screenshots', row.get('file_screenshot', '')) is not None
    or media_path('audio', row.get('file_audio', '')) is not None
]
if not cases:
    st.warning('Tidak ada case untuk agent ini.')
    st.stop()

presentation_key = (selected_date, selected_agent)
if st.session_state.get('hotline_presentation_key') != presentation_key:
    st.session_state.hotline_presentation_key = presentation_key
    st.session_state.hotline_case_index = 0

case_count = len(cases)
case_index = min(st.session_state.hotline_case_index, case_count - 1)
st.session_state.hotline_case_index = case_index
st.subheader(f'{selected_agent} · Case {case_index + 1} of {case_count}')

previous, next_case = st.columns(2)
with previous:
    st.button(
        'Previous case', disabled=case_index == 0,
        on_click=move_case, args=(-1, case_count), use_container_width=True,
    )
with next_case:
    st.button(
        'Next case', disabled=case_index == case_count - 1,
        on_click=move_case, args=(1, case_count), use_container_width=True,
    )

render_case(cases[case_index], case_index + 1)
