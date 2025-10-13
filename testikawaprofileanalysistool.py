import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 백엔드 함수 (변경 없음) ---
def create_new_profile():
    points = list(range(21)); data = {'Point': points, '온도': [np.nan]*len(points), '분': [np.nan]*len(points), '초': [np.nan]*len(points), '구간 시간 (초)': [np.nan]*len(points), '누적 시간 (초)': [np.nan]*len(points), 'ROR (℃/sec)': [np.nan]*len(points)}
    df = pd.DataFrame(data); df.loc[0, ['분', '초', '누적 시간 (초)']] = 0
    return df

def create_new_fan_profile():
    points = list(range(11)); data = {'Point': points, 'Fan (%)': [np.nan]*len(points), '분': [np.nan]*len(points), '초': [np.nan]*len(points), '구간 시간 (초)': [np.nan]*len(points), '누적 시간 (초)': [np.nan]*len(points)}
    df = pd.DataFrame(data); df.loc[0, ['분', '초', '누적 시간 (초)']] = 0
    return df

def sync_profile_data(df, primary_input_mode):
    df = df.reset_index(drop=True); df['Point'] = df.index
    if df['온도'].isnull().all(): return df
    last_valid_index = df['온도'].last_valid_index();
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    if primary_input_mode == '시간 입력':
        calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
        calc_df['구간 시간 (초)'] = calc_df['누적 시간 (초)'].diff().shift(-1)
    elif primary_input_mode == '구간 입력':
        cumulative_seconds = calc_df['구간 시간 (초)'].fillna(0).cumsum()
        calc_df['누적 시간 (초)'] = np.concatenate(([0], cumulative_seconds[:-1].values))
        calc_df['분'] = (calc_df['누적 시간 (초)'] // 60).astype(int)
        calc_df['초'] = (calc_df['누적 시간 (초)'] % 60).astype(int)
    delta_temp = calc_df['온도'].diff(); delta_time = calc_df['누적 시간 (초)'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ROR (℃/sec)'] = ror; df.update(calc_df)
    return df

def sync_fan_data(df, primary_input_mode):
    df = df.reset_index(drop=True); df['Point'] = df.index
    if df['Fan (%)'].isnull().all(): return df
    last_valid_index = df['Fan (%)'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    if primary_input_mode == '시간 입력':
        calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
        calc_df['구간 시간 (초)'] = calc_df['누적 시간 (초)'].diff().shift(-1)
    elif primary_input_mode == '구간 입력':
        cumulative_seconds = calc_df['구간 시간 (초)'].fillna(0).cumsum()
        calc_df['누적 시간 (초)'] = np.concatenate(([0], cumulative_seconds[:-1].values))
        calc_df['분'] = (calc_df['누적 시간 (초)'] // 60).astype(int)
        calc_df['초'] = (calc_df['누적 시간 (초)'] % 60).astype(int)
    df.update(calc_df)
    return df

def calculate_ror(df):
    if df['온도'].isnull().all(): return df
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    delta_temp = calc_df['온도'].diff(); delta_time = calc_df['누적 시간 (초)'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ROR (℃/sec)'] = ror; df.update(calc_df)
    return df

# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title('☕ Ikawa Profile Analysis Tool')
st.markdown("**(v.1.0 2025.10.13)**")

if 'profiles' not in st.session_state or not st.session_state.profiles:
    st.session_state.profiles = {'프로파일 1': create_new_profile(), '프로파일 2': create_new_profile(), '프로파일 3': create_new_profile()}
if 'fan_profiles' not in st.session_state:
    st.session_state.fan_profiles = {name: create_new_fan_profile() for name in st.session_state.profiles.keys()}
if 'processed_profiles' not in st.session_state: st.session_state.processed_profiles = None
if 'processed_fan_profiles' not in st.session_state: st.session_state.processed_fan_profiles = None
if 'graph_button_enabled' not in st.session_state: st.session_state.graph_button_enabled = False
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0

with st.sidebar:
    st.header("⚙️ 보기 옵션")
    profile_names_sidebar = list(st.session_state.profiles.keys())
    # 처음에는 모든 프로파일을 기본값으로 하되, 사용자가 선택한 값이 있으면 그것을 유지
    default_selected = st.session_state.get('selected_profiles', profile_names_sidebar)
    # 만약 저장된 선택값이 현재 프로파일 목록에 없는 경우 (예: 프로파일 삭제 후) 동기화
    default_selected = [p for p in default_selected if p in profile_names_sidebar]
    
    st.session_state.selected_profiles = st.multiselect("그래프에 표시할 프로파일 선택", options=profile_names_sidebar, default=default_selected)
    
    st.subheader("축 범위 조절")
    col1, col2 = st.columns(2)
    with col1:
        x_min = st.number_input("X축 최소값", value=0); y_min = st.number_input("Y축(온도) 최소값", value=85); y2_min = st.number_input("보조Y축(ROR) 최소값", value=0.0, format="%.2f")
    with col2:
        x_max = st.number_input("X축 최대값", value=360); y_max = st.number_input("Y축(온도) 최대값", value=235); y2_max = st.number_input("보조Y축(ROR) 최대값", value=0.75, format="%.2f")
    st.session_state.axis_ranges = {'x': [x_min, x_max], 'y': [y_min, y_max], 'y2': [y2_min, y2_max]}

st.subheader("프로파일 관리")
if len(st.session_state.profiles) < 10:
    if st.button("＋ 새 프로파일 추가"):
        existing_nums = [int(name.split(' ')[1]) for name in st.session_state.profiles.keys() if name.startswith("프로파일 ") and name.split(' ')[1].isdigit()]
        new_profile_num = max(existing_nums) + 1 if existing_nums else 1
        new_name = f"프로파일 {new_profile_num}"; st.session_state.profiles[new_name] = create_new_profile(); st.session_state.fan_profiles[new_name] = create_new_fan_profile(); st.rerun()
else: st.warning("최대 10개의 프로파일까지 추가할 수 있습니다.")
st.divider()

profile_names = list(st.session_state.profiles.keys())
cols = st.columns(len(profile_names))
for i, col in enumerate(cols):
    current_name = profile_names[i]
    with col:
        # (이하 데이터 입력 UI 코드는 이전과 동일)
        col1, col2 = st.columns([0.8, 0.2]);
        with col1: new_name = st.text_input("프로파일 이름", value=current_name, key=f"name_input_{current_name}", label_visibility="collapsed")
        with col2:
            if st.button("삭제", key=f"delete_button_{current_name}"):
                del st.session_state.profiles[current_name]
                if current_name in st.session_state.fan_profiles: del st.session_state.fan_profiles[current_name]
                st.rerun()
        if new_name != current_name:
            if new_name in st.session_state.profiles: st.error("이름 중복!")
            elif not new_name: st.error("이름은 비워둘 수 없습니다.")
            else:
                new_profiles = {new_name if name == current_name else name: df for name, df in st.session_state.profiles.items()}
                new_fan_profiles = {new_name if name == current_name else name: df for name, df in st.session_state.fan_profiles.items()}
                st.session_state.profiles, st.session_state.fan_profiles = new_profiles, new_fan_profiles; st.rerun()
        st.divider()
        main_input_method = st.radio("입력 방식", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        st.subheader("온도 데이터 입력")
        if main_input_method == "구간 입력":
             st.info("구간(초): 현재 포인트에서 다음 포인트까지 걸릴 시간")
        column_config = { "Point": None, "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"), "누적 시간 (초)": st.column_config.NumberColumn("누적 시간(초)", disabled=True), "ROR (℃/sec)": st.column_config.NumberColumn("ROR", format="%.3f", disabled=True)}
        default_visible_cols = ["온도"]
        if main_input_method == "시간 입력": default_visible_cols += ["분", "초"]
        else: default_visible_cols += ["구간 시간 (초)"]
        edited_df = st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=f"editor_{main_input_method}_{current_name}", hide_index=True, num_rows="dynamic", column_order=default_visible_cols)
        if st.button("🔄 온도 데이터 동기화", key=f"sync_button_{current_name}"):
            synced_df = sync_profile_data(edited_df, main_input_method); st.session_state.profiles[current_name] = synced_df; st.session_state.graph_button_enabled = True; st.rerun()
        with st.expander("팬 데이터 입력 (선택 사항)"):
            fan_df = st.session_state.fan_profiles.get(current_name, create_new_fan_profile())
            fan_column_config = {"Point": None, "Fan (%)": st.column_config.NumberColumn("팬(%)", min_value=0, max_value=100), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"), "누적 시간 (초)": st.column_config.NumberColumn("누적(초)", disabled=True)}
            fan_visible_cols = ["Fan (%)"]
            if main_input_method == "시간 입력": fan_visible_cols += ["분", "초"]
            else: fan_visible_cols += ["구간 시간 (초)"]
            fan_edited_df = st.data_editor(fan_df, column_config=fan_column_config, column_order=fan_visible_cols, num_rows="dynamic", key=f"fan_editor_{current_name}", hide_index=True)
            if st.button("🔄 팬 데이터 동기화", key=f"fan_sync_button_{current_name}"):
                synced_fan_df = sync_fan_data(fan_edited_df, main_input_method); st.session_state.fan_profiles[current_name] = synced_fan_df; st.session_state.graph_button_enabled = True; st.rerun()
st.divider()

st.header("📈 그래프 및 분석")
# --- 여기가 수정된 부분 ---
if st.button("📊 그래프 업데이트", disabled=not st.session_state.graph_button_enabled):
    # 데이터가 있는 프로파일만 자동으로 선택하도록 session_state 업데이트
    profiles_with_data = [name for name, df in st.session_state.profiles.items() if not df['온도'].dropna().empty]
    if profiles_with_data:
        st.session_state.selected_profiles = profiles_with_data
    
    st.session_state.processed_profiles = {name: calculate_ror(df.copy()) for name, df in st.session_state.profiles.items()}
    st.session_state.processed_fan_profiles = {name: df.copy() for name, df in st.session_state.fan_profiles.items()}
    st.session_state.selected_time = 0
    st.rerun() # 선택된 프로파일을 사이드바에 즉시 반영하기 위해 한번 더 실행

if st.session_state.processed_profiles:
    graph_col, analysis_col = st.columns([0.7, 0.3])
    max_time_temp = max((df['누적 시간 (초)'].max() for df in st.session_state.processed_profiles.values() if not df['누적 시간 (초)'].dropna().empty), default=0)
    max_time_fan = max((df['누적 시간 (초)'].max() for df in st.session_state.processed_fan_profiles.values() if not df['누적 시간 (초)'].dropna().empty), default=0)
    max_time = max(max_time_temp, max_time_fan, 1)
    with graph_col:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05, specs=[[{"secondary_y": True}], [{"secondary_y": False}]])
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(profile_names)}
        for name in selected_profiles_data:
            df = st.session_state.processed_profiles.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                valid_df = df.dropna(subset=['누적 시간 (초)', '온도']);
                if len(valid_df) > 1:
                    fig.add_trace(go.Scatter(x=valid_df['누적 시간 (초)'], y=valid_df['온도'], mode='lines+markers', name=name, line=dict(color=color), legendgroup=name), row=1, col=1, secondary_y=False)
                    ror_df = valid_df.iloc[1:]
                    fig.add_trace(go.Scatter(x=ror_df['누적 시간 (초)'], y=ror_df['ROR (℃/sec)'], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), legendgroup=name, showlegend=False), row=1, col=1, secondary_y=True)
            fan_df = st.session_state.processed_fan_profiles.get(name)
            if fan_df is not None and color is not None:
                valid_fan_df = fan_df.dropna(subset=['누적 시간 (초)', 'Fan (%)'])
                if len(valid_fan_df) > 1:
                    fig.add_trace(go.Scatter(x=valid_fan_df['누적 시간 (초)'], y=valid_fan_df['Fan (%)'], mode='lines+markers', name=f'{name} Fan', line=dict(color=color, dash='solid'), legendgroup=name, showlegend=False), row=2, col=1)
        selected_time_int = int(st.session_state.get('selected_time', 0)); fig.add_vline(x=selected_time_int, line_width=1, line_dash="dash", line_color="grey")
        axis_ranges = st.session_state.get('axis_ranges', {'x': [0, 360], 'y': [85, 235], 'y2': [0, 0.75]})
        fig.update_layout(height=900, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig.update_xaxes(range=axis_ranges['x'], title_text=None, showticklabels=False, dtick=60, row=1, col=1)
        fig.update_xaxes(range=axis_ranges['x'], title_text='시간 (초)', dtick=60, row=2, col=1)
        fig.update_yaxes(title_text="온도 (°C)", range=axis_ranges['y'], dtick=10, row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="ROR (℃/sec)", range=axis_ranges['y2'], showgrid=False, row=1, col=1, secondary_y=True)
        fig.update_yaxes(title_text="팬 (%)", range=[60, 90], row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
    with analysis_col:
        st.subheader("🔍 분석 정보"); st.markdown("---")
        st.write("**총 로스팅 시간**")
        for name in selected_profiles_data:
            df = st.session_state.processed_profiles.get(name)
            if df is not None:
                valid_df = df.dropna(subset=['누적 시간 (초)'])
                if not valid_df.empty:
                    total_time = valid_df['누적 시간 (초)'].max(); time_str = f"{int(total_time // 60)}분 {int(total_time % 60)}초"
                    st.markdown(f"**{name}**: <span style='font-size: 1.1em;'>{time_str}</span>", unsafe_allow_html=True)
        st.markdown("---")
        def update_slider_time():
            st.session_state.selected_time = st.session_state.time_slider
        selected_time_val = st.session_state.get('selected_time', 0)
        st.slider("시간 선택 (초)", 0, int(max_time), selected_time_val, 1, key="time_slider", on_change=update_slider_time)
        st.write(""); st.write("**선택된 시간 상세 정보**")
        selected_time = st.session_state.selected_time; st.markdown(f"#### {int(selected_time // 60)}분 {int(selected_time % 60):02d}초 ({selected_time}초)")
        for name in selected_profiles_data:
            st.markdown(f"<p style='margin-bottom: 0.2em;'><strong>{name}</strong></p>", unsafe_allow_html=True)
            temp_str, ror_str, fan_str = "--", "--", "--"
            df = st.session_state.processed_profiles.get(name)
            if df is not None:
                valid_df = df.dropna(subset=['누적 시간 (초)', '온도', 'ROR (℃/sec)'])
                if len(valid_df) > 1 and selected_time <= valid_df['누적 시간 (초)'].max():
                    hover_temp = np.interp(selected_time, valid_df['누적 시간 (초)'], valid_df['온도']); hover_ror = np.interp(selected_time, valid_df['누적 시간 (초)'], valid_df['ROR (℃/sec)'])
                    temp_str, ror_str = f"{hover_temp:.1f}℃", f"{hover_ror:.3f}℃/sec"
            fan_df = st.session_state.processed_fan_profiles.get(name)
            if fan_df is not None:
                valid_fan_df = fan_df.dropna(subset=['누적 시간 (초)', 'Fan (%)'])
                if len(valid_fan_df) > 1 and selected_time <= valid_fan_df['누적 시간 (초)'].max():
                    hover_fan = np.interp(selected_time, valid_fan_df['누적 시간 (초)'], valid_fan_df['Fan (%)']); fan_str = f"{hover_fan:.1f}%"
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• 온도: {temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• ROR: {ror_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin-bottom:0.8em; font-size: 0.95em;'>&nbsp;&nbsp;• 팬: {fan_str}</p>", unsafe_allow_html=True)

with st.expander("🕒 포인트별 분석 보기"):
    if st.session_state.processed_profiles:
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        for name in selected_profiles_data:
            st.subheader(f"{name} 포인트별 분석")
            temp_df = st.session_state.processed_profiles.get(name)
            fan_df = st.session_state.processed_fan_profiles.get(name)
            if temp_df is not None and fan_df is not None:
                st.write("**온도 포인트**")
                temp_analysis_df = temp_df.dropna(subset=['온도']).copy()
                if not temp_analysis_df.empty and not fan_df.dropna(subset=['Fan (%)']).empty and len(fan_df.dropna(subset=['Fan (%)'])) > 1:
                    temp_analysis_df['Fan (%)'] = np.interp(temp_analysis_df['누적 시간 (초)'], fan_df['누적 시간 (초)'].dropna(), fan_df['Fan (%)'].dropna()).round(1)
                temp_cols_order = ['온도', 'Fan (%)', '분', '초', '구간 시간 (초)', '누적 시간 (초)', 'ROR (℃/sec)']
                col1, col2 = st.columns([0.65, 0.35])
                with col1:
                    st.data_editor(temp_analysis_df, column_order=temp_cols_order, hide_index=True, disabled=True, use_container_width=True, key=f"temp_analysis_table_{name}")

                st.write("**팬 포인트**")
                fan_analysis_df = fan_df.dropna(subset=['Fan (%)']).copy()
                if not fan_analysis_df.empty and not temp_df.dropna(subset=['온도']).empty and len(temp_df.dropna(subset=['온도'])) > 1:
                    fan_analysis_df['온도'] = np.interp(fan_analysis_df['누적 시간 (초)'], temp_df['누적 시간 (초)'].dropna(), temp_df['온도'].dropna()).round(1)
                    fan_analysis_df['ROR (℃/sec)'] = np.interp(fan_analysis_df['누적 시간 (초)'], temp_df['누적 시간 (초)'].dropna(), temp_df['ROR (℃/sec)'].dropna()).round(3)
                fan_cols_order = ['온도', 'Fan (%)', '분', '초', '구간 시간 (초)', '누적 시간 (초)', 'ROR (℃/sec)']
                col3, col4 = st.columns([0.65, 0.35])
                with col3:
                    st.data_editor(fan_analysis_df, column_order=fan_cols_order, hide_index=True, disabled=True, use_container_width=True, key=f"fan_analysis_table_{name}")
    else:
        st.info("먼저 데이터를 입력하고 '그래프 업데이트' 버튼을 눌러주세요.")
