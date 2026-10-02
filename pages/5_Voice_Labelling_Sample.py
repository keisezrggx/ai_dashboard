from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")


@st.cache_data
def load_csv(path, modified_ns, file_size):
    return pd.read_csv(path)


def media_path(folder, filename):
    if pd.isna(filename) or str(filename).strip() in ('', '-'):
        return None
    return Path(folder) / str(filename).strip()


def move_case(step, count):
    st.session_state.voice_case_index = max(
        0, min(st.session_state.voice_case_index + step, count - 1)
    )


st.title('Voice Labelling')
try:
    with st.spinner('Loading meeting cases...'):
        csv_path = Path('dataset_qc/sampling_voice_labelling.csv')
        csv_stat = csv_path.stat()
        df = load_csv(str(csv_path), csv_stat.st_mtime_ns, csv_stat.st_size)
except (OSError, pd.errors.ParserError) as exc:
    st.error(f'Could not load meeting cases: {exc}')
    st.stop()

required_columns = {'tanggal_meeting', 'checker', 'file_screenshot', 'file_audio'}
missing_columns = required_columns - set(df.columns)
if missing_columns:
    st.error(f'Missing CSV columns: {", ".join(sorted(missing_columns))}')
    st.stop()

df['tanggal_meeting'] = pd.to_datetime(df['tanggal_meeting'], errors='coerce').dt.date
meeting_data = {}
for _, row in df.iterrows():
    meeting_date = row['tanggal_meeting']
    checker = row['checker']
    if pd.isna(meeting_date) or pd.isna(checker) or not str(checker).strip():
        continue

    screenshot = media_path('screenshots', row['file_screenshot'])
    audio = media_path('audio', row['file_audio'])
    if screenshot is None and audio is None:
        continue

    entry = {
        'checker': str(checker).strip(),
        'screenshot': screenshot,
        'audio': audio,
        'result': row.get('result'),
        'notes': row.get('notes'),
        'identifier': row.get('id annotating'),
    }
    meeting_data.setdefault(meeting_date, []).append(entry)

if not meeting_data:
    st.warning('Tidak ada data meeting.')
    st.stop()

dates = sorted(meeting_data, reverse=True)
if len(dates) == 1:
    selected_date = dates[0]
else:
    selected_date = st.sidebar.date_input(
        'Tanggal Meeting', value=dates[0], min_value=dates[-1], max_value=dates[0]
    )

if selected_date not in meeting_data:
    st.warning(f'No meeting data for {selected_date.strftime("%d %B %Y")}. Choose a meeting date.')
    st.stop()

st.caption(f'Meeting date: {selected_date.strftime("%d %B %Y")}')
manual_order = ['Neneng', 'Aul', 'Azer', 'Reza']
available_checkers = {entry['checker'] for entry in meeting_data[selected_date]}
checker_list = [name for name in manual_order if name in available_checkers]
checker_list += sorted(available_checkers - set(checker_list))
selected_checker = st.radio('Presenter', checker_list, horizontal=True)

filtered_entries = [
    entry for entry in meeting_data[selected_date]
    if entry['checker'] == selected_checker
]
presentation_key = (selected_date, selected_checker)
if st.session_state.get('voice_presentation_key') != presentation_key:
    st.session_state.voice_presentation_key = presentation_key
    st.session_state.voice_case_index = 0

case_count = len(filtered_entries)
case_index = st.session_state.voice_case_index
item = filtered_entries[case_index]
st.subheader(f'{selected_checker} · Case {case_index + 1} of {case_count}')

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

image_column, audio_column = st.columns([2.5, 1], gap='large')
with image_column:
    st.markdown('#### Segments')
    screenshot = item['screenshot']
    if screenshot is None:
        st.info('Screenshot not provided for this case.')
    elif not screenshot.is_file():
        st.warning(f'Screenshot file not found: {screenshot.name}')
    else:
        try:
            st.image(str(screenshot), use_container_width=True)
        except Exception:
            st.error(f'Could not display screenshot: {screenshot.name}')

with audio_column:
    st.markdown('#### Audio')
    audio = item['audio']
    if audio is None:
        st.info('Audio not provided for this case.')
    elif not audio.is_file():
        st.warning(f'Audio file not found: {audio.name}')
    else:
        try:
            st.audio(str(audio))
        except Exception:
            st.error(f'Could not play audio: {audio.name}')

    result = item['result']
    if pd.notna(result) and str(result).strip():
        st.write(f'Result: {str(result).strip()}')
    notes = item['notes']
    if pd.notna(notes) and str(notes).strip():
        st.write(f'Notes: {str(notes).strip()}')
    identifier = item['identifier']
    if pd.notna(identifier) and str(identifier).strip():
        st.caption(f'ID: {str(identifier).strip()}')