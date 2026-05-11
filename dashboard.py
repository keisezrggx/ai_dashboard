import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import logging
import datetime

# from backend.kula.chatbot_optimized import ChatbotOptimized
from utils_aggregation import aggregation_ratio, aggregate_sum, sidebar_filters, aggregate_table_with_granularity, calculate_checker_accuracy, aggregate_checker_errors, week_of_month, aggregate_csat_dual, highlight_diff_words, build_screenshot_path, show_image
from streamlit_chatbox import *
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder
from datetime import datetime, timedelta

logging.getLogger('streamlit.runtime.scriptrunner').setLevel(logging.ERROR)

CURRENT_THEME = "light" 
IS_DARK_THEME = False
st.set_page_config(layout="wide")

# team = st.sidebar.radio('Team', ['QC'])
team = 'QC'

if team == 'QC':
    st.sidebar.header("Adjust Data")

    # page = st.sidebar.selectbox("Pages", ["Agent Sample", "Hotline Calibration"])
    page = 'Hotline Calibration'


    #Page 1
    if page == "Overview":
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
        df = pd.read_csv('dataset_qc/new_4_clean.csv', parse_dates=['Tanggal Pengerjaan', 'Waktu Inbound'])

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

            # Total Tagged berdasarkan pertambahan dari hari sebelumnya
            last_selected_date = date_range[1]
            day_before_last = last_selected_date - pd.Timedelta(days=1)

            # Hitung total data sampai hari sebelum tanggal terakhir
            total_before = df[
                (df['Tanggal Pengerjaan'].dt.date >= date_range[0]) &
                (df['Tanggal Pengerjaan'].dt.date <= day_before_last)
            ]
            count_before = len(total_before)

            # Hitung total data sampai tanggal terakhir
            total_until_last = df[
                (df['Tanggal Pengerjaan'].dt.date >= date_range[0]) &
                (df['Tanggal Pengerjaan'].dt.date <= last_selected_date)
            ]
            count_until_last = len(total_until_last)

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

            # Efektif Score Cards
            efektif_list = ['On Target/HC', 'On Target/Not HC', 'Miss Target/ Not HC', 'Miss Target/HC']
            last_selected_date = date_range[1]
            day_before_last = last_selected_date - pd.Timedelta(days=1)

            for i, label in enumerate(efektif_list):
                # Total hingga tanggal terakhir
                count_until_last = df[
                    (df['Tanggal Pengerjaan'].dt.date >= date_range[0]) &
                    (df['Tanggal Pengerjaan'].dt.date <= last_selected_date) &
                    (df['Efektif'] == label)
                ].shape[0]

                # Total hingga hari sebelumnya
                count_before = df[
                    (df['Tanggal Pengerjaan'].dt.date >= date_range[0]) &
                    (df['Tanggal Pengerjaan'].dt.date <= day_before_last) &
                    (df['Efektif'] == label)
                ].shape[0]

                delta = count_until_last - count_before
                if delta > 0:
                    delta_color = "normal"
                elif delta < 0:
                    delta_color = "inverse"
                else:
                    delta_color = "off"
                with cols[i + 1]:
                    st.markdown('<div class="metric-box">', unsafe_allow_html=True)
                    styled_metric(label, f"{count_until_last:,}", delta, delta_color)
                    st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            "<h5 style='text-align: center;'>Current AI Accuracy: 95.43%</h5>",
            unsafe_allow_html=True
            )

        # Line Chart Graphic
        with st.container():

            df_weekly = df_filtered.copy()
            df_weekly['Week'] = df_weekly['Tanggal Pengerjaan'].dt.to_period('W').apply(lambda r: r.start_time)

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
    elif page == "Sampling":
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

        df_sampling = pd.read_csv('dataset_qc/kalib_sampling.csv', parse_dates=['Tanggal Sampling'])

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

        # ==== Filter RED LABEL ====
        df_merah = df_sampling[
            df_sampling['Red Label'].str.upper().isin(["MERAH", "TEXT"])
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

            # === Jumlah Hari Ini ===
            total_this_day = df_this_day.shape[0]
            merah_this_day = df_this_day[
                df_this_day['Red Label'].str.upper().str.contains('MERAH') +
                df_this_day['Red Label'].str.upper().str.contains('TEXT')
                ].shape[0]

            non_merah_this_day = df_this_day[df_this_day['Red Label'].str.upper() != 'MERAH'].shape[0]

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
        df_sampling['Week'] = df_sampling['Tanggal Sampling'].dt.to_period('W').apply(lambda r: r.start_time)

        # Pisahkan berdasarkan Red Label
        df_merah = df_sampling[df_sampling['Red Label'].str.upper() == "MERAH"]
        df_text = df_sampling[df_sampling['Red Label'].str.upper() == "TEXT"]

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

            total_merah = df_sampling['Red Label'].str.upper().isin(['MERAH', 'TEXT']).sum()
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

            # Pisahkan berdasarkan Red Label
            df_merah = df_last7[df_last7['Red Label'].str.upper() == "MERAH"]
            df_text = df_last7[df_last7['Red Label'].str.upper() == "TEXT"]

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
    elif page == "Audio Sample":
        st.title("Audio Sample")

        # Load data
        df = pd.read_csv("dataset_qc/weekly_calibration_data.csv")
        df.columns = df.columns.str.strip()
        df = df.fillna("")
        df["Tanggal Meeting"] = pd.to_datetime(df["Tanggal Meeting"], errors="coerce").dt.date

        meeting_data = {}

        for _, row in df.iterrows():
            tanggal_meeting = row["Tanggal Meeting"]
            checker = row["Checker"]
            agent = row["Agent Sampling"]

            # Ambil nama file audio
            audio_filename = str(row.get("File Audio", "")).strip()
            audio_file = f"audio/{audio_filename}" if audio_filename else None

            # Siapkan teks kalibrasi
            sections = []

            mapping = [
                ("Hasil ASR", "Text Awal Hasil ASR", "ASR"),
                ("Hasil Pemeriksaan Kualitas", "Text Awal Hasil Pemeriksaan Kualitas", "Hasil Pemeriksaan Kualitas" ),
                ("Efektif", "Text Awal Efektif", "Efektif"),
                ("Kejelasan Suara", "Text Awal Kejelasan Suara", "Kejelasan Suara"),
                ("Suara Lain", "Text Awal Suara Lain", "Suara Lain"),
                ("Kelengkapan Rekaman", "Text Awal Kelengkapan Rekaman", "Kelengkapan Rekaman"),
                ("Revisi Teks", "Text Awal Revisi Text", "Teks")
            ]

            for final_col, awal_col, label in mapping:
                text_awal = str(row[awal_col]).strip()
                hasil = str(row[final_col]).strip()

                if text_awal:
                    if label == "Teks" and hasil:
                        hasil_diff = highlight_diff_words(text_awal, hasil)
                        hasil_markdown = f"**{label}:** {text_awal}  \n**Diubah:** <span>{hasil_diff}</span>  \n"
                        sections.append(hasil_markdown)
                    else:
                        sections.append(f"**{label}:** {text_awal}  \n**Diubah:** {hasil}  \n")


            if not sections and not audio_filename:
                continue

            entry = {
                "checker": checker,
                "agent": agent,
                "text": f"**Checker:** {checker}" + ("\n\n" + "\n".join(sections) if sections else ""),
                "file": audio_file
            }

            if tanggal_meeting not in meeting_data:
                meeting_data[tanggal_meeting] = []

            meeting_data[tanggal_meeting].append(entry)


        # === Sidebar: Pilih tanggal ===
        selected_date = st.sidebar.date_input(
            "Tanggal Meeting",
            value=max(meeting_data.keys()),  #default
            min_value=min(meeting_data.keys()),
            max_value=max(meeting_data.keys())
        )

        if selected_date not in meeting_data:
            st.warning(f"Tidak ada data untuk tanggal {selected_date.strftime('%d %B %Y')}.")
            st.stop()

        # Date filter
        manual_order = ["Neneng", "Azer", "Reza", "Aulia"]
        agent_list = [agent for agent in manual_order if agent in {entry["agent"] for entry in meeting_data[selected_date]}]
        selected_agent = st.sidebar.radio("Agent Sampling", agent_list)

        st.markdown(f"### {selected_agent}")

        filtered_entries = [
            item for item in meeting_data[selected_date]
            if item["agent"] == selected_agent
        ]

        for i in range(0, len(filtered_entries), 3):
            row_entries = filtered_entries[i:i+3]
            cols = st.columns(3)

            for col, item in zip(cols, row_entries):
                with col:
                    with st.expander(f"Audio {i + filtered_entries.index(item) + 1}"):
                        st.markdown(item["text"], unsafe_allow_html=True)
                        if item["file"]:
                            try:
                                st.audio(item["file"])
                            except Exception as e:
                                st.error(f"Audio Restricted")


    # Page 4
    elif page == "Agent Sample":
        st.title("AI Human Agent QC Sampling")
        
        # Load data
        df = pd.read_csv("dataset_qc/sampling_agent.csv")
        # df = pd.read_csv('dataset_qc/sampling_summary.csv')
        df.columns = df.columns.str.strip()
        df.fillna('-', inplace=True)
        df['tanggal_pengerjaan'] = pd.to_datetime(df['tanggal_pengerjaan'], 
        errors='coerce').dt.date
        df['tanggal_meeting'] = pd.to_datetime(df['tanggal_meeting'], errors='coerce').dt.date

        meeting_data = {}

        for _, row in df.iterrows():
            tanggal_meeting = row['tanggal_meeting']
            checker = row['nama_qc']
            agent = row['nama_sampling']

            # Ambil nama file gambar
            screenshot_file_1 = build_screenshot_path(row.get('file_screenshot', ''))
            screenshot_file_2 = build_screenshot_path(row.get('file_screenshot_2', ''))
            screenshot_file_3 = build_screenshot_path(row.get('file_screenshot_3', ''))

            # Siapkan teks recheck
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
                    'col': 'chat_id',
                    'label': 'Chat ID'
                },

                {
                    'type': 'static',
                    'col': 'code_robot',
                    'label': 'Code Robot'
                },

                {
                    'type': 'static',
                    'col': 'description',
                    'label': 'Description'
                },

                # dynamic data
                {
                    'type': 'compare',
                    'final': 'result_qc_ubah', 
                    'text_awal': 'result_qc', 
                    'label': 'Result QC'
                },
                
                {
                    'type': 'compare',
                    'final': 'reason_ubah',
                    'text_awal': 'reason', 
                    'label': 'Reason'
                },
            ]

            asi_afi = str(row.get("asi/afi", "")).strip()
            chat_id = str(row.get("chat_id", "")).strip()
            code_robot = str(row.get("code_robot", "")).strip()
            description = str(row.get("description", "")).strip()

            if asi_afi and chat_id:
                sections.append(
                    f"**Comp:** {asi_afi}  \n **Chat ID:** {chat_id}  \n **Code Robot:** {code_robot}  \n"
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

            # for item in mapping:
            #     if item['type'] == 'compare':
                    
            #         text_awal = str(row.get(item['text_awal'], '')).strip()
            #         hasil = str(row.get(item['final'], '')).strip()

            #         if text_awal:
            #             if item['label'] == 'Revisi Sentimen':
            #                 sections.append(
            #                     f'**Robot Tag:** {sentimen_pengguna}  \n'
            #                     f"**{item['label']}:** {text_awal}  \n"
            #                     f'**Sampling:** {hasil}   \n'
            #                 )
            #             else:
            #                 sections.append(
            #                     f'**Alasan Revisi:** {text_awal}  \n'
            #                     f'**Alasan Sampling:** {hasil}   \n'
            #                 )
            
            if not sections and not (screenshot_file_1 or screenshot_file_2):
                continue

            entry = {
                'checker': checker,
                'agent': agent,
                'text': f'**Checker:** {checker}' + ('\n\n' + '\n'.join(sections) if sections else ''),
                'file_1': screenshot_file_1,
                'file_2': screenshot_file_2,
                'file_3': screenshot_file_3
            }

            if tanggal_meeting not in meeting_data:
                meeting_data[tanggal_meeting] = []

            meeting_data[tanggal_meeting].append(entry)

        dates = sorted(meeting_data.keys())

        if not dates:
            st.warning('Tidak ada data meeting.')
            st.stop() 

        # === Sidebar: Pilih Tanggal ===
        selected_date = st.sidebar.date_input(
            'Tanggal Meeting',
            value=max(meeting_data.keys()),
            min_value=min(meeting_data.keys()),
            max_value=max(meeting_data.keys())
        )

        if selected_date not in meeting_data:
            st.warning(f'Tidak ada data untuk tanggal {selected_date.strftime('%d %B %Y')}')
            st.stop()

        # Date filter
        manual_order = ['Neneng', 'Aul', 'Reza', 'Azer']
        agent_list = [agent for agent in manual_order if agent in {entry['agent'] for entry in meeting_data[selected_date]}]
        selected_agent = st.sidebar.radio('Agent Sampling', agent_list)

        st.markdown(f"### {selected_agent}")

        filtered_entries = [
            item for item in meeting_data[selected_date]
            if item['agent'] == selected_agent
        ]

        for i in range(0, len(filtered_entries), 3):
            row_entries = filtered_entries[i:i+3]
            cols =  st.columns(len(row_entries))

            for idx, item in enumerate(filtered_entries, start=1):

                    head_case, head_s = st.columns([0.8, 1.2])
                    
                    with head_case:
                        with st.expander(f'Case {idx}', expanded=False):
                            st.markdown(item['text'], unsafe_allow_html=True)
                            
                    with head_s:
                        with st.expander(f'Screenshot {idx} - 1', expanded=False):
                            show_image(item.get('file_1'))
                        
                        with st.expander(f'Screenshot {idx} - 2', expanded=False):
                            show_image(item.get('file_2'))
                        
                        with st.expander(f'Screenshot {idx} - 3', expanded=False):
                            show_image(item.get('file_3'))


    # Page 5
    elif page == 'Performance':
        df_sampling = pd.read_csv(
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
    elif page == 'Hotline Calibration':
        st.title('Hotline Calibration')
        df = pd.read_csv('dataset_qc/sampling_hotline.csv')

        df.fillna('-', inplace=True)
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
        manual_order = ['Reza', 'Neneng', 'Azer', 'Aulia']
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
                            if not item['file_audio']:
                                st.error('Audio Restricted')
                            try:
                                st.audio(item['file_audio'])
                            except Exception as e:
                                st.info('No Audio')

                with head_s:
                    with st.expander(f'Screenshot {idx} - 1', expanded=False):
                        show_image(item.get('file_1'))

elif team == 'KULA':
    # st.markdown('#####')

    page = st.sidebar.selectbox("Pages", ['Dashboard'])

    if page == 'Dashboard':
        
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
        df_ratio = pd.read_csv('dataset_kula/success_ratio.csv')
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
        
        csat_before = pd.read_csv('dataset_kula/csat_before_takeout.csv')
        csat_after = pd.read_csv('dataset_kula/csat_after_takeout.csv')

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
        df_bad_survey = pd.read_csv('dataset_kula/bad_survey.csv')

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
                gd1 = GridOptionsBuilder.from_dataframe(subcat_summary)
                for col in subcat_summary.columns:
                    gd1.configure_columns(col, filter=False, sortable=True, resizable=True)
                gd1.configure_pagination()
                grid_options1 = gd1.build()
                AgGrid(subcat_summary, gridOptions=grid_options1, height=300)

            with cols[1]:
                gd2 = GridOptionsBuilder.from_dataframe(cat_summary)
                for col in cat_summary.columns:
                    gd2.configure_column(col, filter=False, sortable=True, resizable=True)
                gd2.configure_pagination()
                grid_options2 = gd2.build()
                AgGrid(cat_summary, gridOptions=grid_options2, height=300)

        # Like and Dislike
        st.markdown('##### Like and Dislike')
        with st.container():
            cols = st.columns([1,4])
            
            #The Linechart
            df_like_dislike = pd.read_csv('dataset_kula/kula_like_dislike.csv')
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
                id_vars = 'Date',
                value_vars = ['Like', 'Dislike'],
                var_name = 'Category',
                value_name = 'Total'
            )
            
            #The BarGraph Chart
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
                gd1 = GridOptionsBuilder.from_dataframe(team_summary)
                for col in team_summary.columns:
                    gd1.configure_column(col, filter=False, sortable=True, resizable=True)
                gd1.configure_pagination()
                grid_options1 = gd1.build()
                AgGrid(team_summary, gridOptions=grid_options1, height=400)

            with cols[1]:
                gd2 = GridOptionsBuilder.from_dataframe(bg_summary)
                for col in bg_summary.columns:
                    gd2.configure_column(col, filter=False, sortable=True, resizable=True)
                gd2.configure_pagination()
                grid_options2 = gd2.build()
                AgGrid(bg_summary, gridOptions=grid_options2, height=400)

        
            # Table QC KULA
            df_qc_kula = pd.read_csv('dataset_kula/qc_kula.csv')
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
                    gd_main = GridOptionsBuilder.from_dataframe(main_sub_summary)
                    for col in main_sub_summary.columns:
                        gd_main.configure_column(col, filter=False, sortable=True, resizable=True)
                    gd_main.configure_pagination()
                    grid_options_main = gd_main.build()
                    AgGrid(main_sub_summary, gridOptions=grid_options_main, height=400)

                with cols[1]:
                    gd_team = GridOptionsBuilder.from_dataframe(team_cat_qc)
                    for col in team_cat_qc.columns:
                        gd_team.configure_column(col, filter=False, sortable=True, resizable=True)
                    gd_team.configure_pagination()
                    grid_options_team = gd_team.build()
                    AgGrid(team_cat_qc, gridOptions=grid_options_team, height=400)
            
            with st.container():
                cols = st.columns([3,2])

                with cols[0]:
                    gd_bg = GridOptionsBuilder.from_dataframe(bg_summary)
                    for col in bg_summary.columns:
                        gd_bg.configure_column(col, filter=False, sortable=True, resizable=True)
                    gd_bg.configure_pagination()
                    grid_options_bg = gd_bg.build()
                    AgGrid(bg_summary, gridOptions=grid_options_bg, height=400)


elif team == 'LLM':
    st.title('LLM QC Report')
    