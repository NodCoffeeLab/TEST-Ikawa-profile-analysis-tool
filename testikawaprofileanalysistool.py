import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 백엔드 함수 ---
def create_new_profile():
    points = list(range(21)); data = {'Point': points, '온도': [np.nan]*len(points), '분': [np.nan]*len(points), '초': [np.nan]*len(points), '구간 시간 (초)': [np.nan]*len(points), '누적 시간 (초)': [np.nan]*len(points), 'ROR (℃/sec)': [np.nan]*len(points)}
    df = pd.DataFrame(data); df.loc[0, ['분', '초', '누적 시간 (초)']] = 0
    return df

def create_new_fan_profile():
    points = list(range(11)); data = {'Point': points, 'Fan (%)': [np.nan]*len(points), '분': [np.nan]*len(points), '초': [np.nan]*len(points), '누적 시간 (초)': [np.nan]*len(points)}
    df = pd.DataFrame(data); df.loc[0, ['분', '초', '누적 시간 (초)']] = 0
    return df

def sync_profile_data(df, primary_input_mode):
    df = df.reset_index(drop=True); df['Point'] = df.index
    if df['온도'].isnull().all(): return df
    last_valid_index = df['온도'].last_valid_index()
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

def sync_fan_data(df):
    df = df.reset_index(drop=True); df['Point'] = df.index
    if df['Fan (%)'].isnull().all(): return df
    last_valid_index = df['Fan (%)'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
    df.update(calc_df)
    return df

def parse_excel_data(text_data, mode):
    new_data = []; lines = text_data.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip(): continue
        parts = line.strip().split(); row = {'Point': i}
        try:
            if mode == '시간 입력':
                if len(parts) >= 3: row['온도'], row['분'], row['초'] = float(parts[0]), int(parts[1]), int(parts[2])
                elif len(parts) >= 1: row['온도'], row['분'], row['초'] = float(parts[0]), 0, 0
            elif mode == '구간 입력':
                if len(parts) >= 2: row['온도'], row['구간 시간 (초)'] = float(parts[0]), int(parts[1])
                elif len(parts) >= 1: row['온도'], row['구간 시간 (초)'] = float(parts[0]), np.nan
            new_data.append(row)
        except (ValueError, IndexError): continue
    if not new_data: return pd.DataFrame()
    return pd.DataFrame(new_data).set_index('Point')

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
st.title('☕ Ikawa Profile Analysis Tool (25.10.08)')

# --- Session State 초기화 ---
if 'profiles' not in st.session_state or not st.session_state.profiles:
    st.session_state.profiles = {'프로파일 1': create_new_profile(), '프로파일 2': create_new_profile(), '프로파일 3': create_new_profile()}
if 'fan_profiles' not in st.session_state:
    st.session_state.fan_profiles = {name: create_new_fan_profile() for name in st.session_state.profiles.keys()}
if 'processed_profiles' not in st.session_state: st.session_state.processed_profiles = None
if 'graph_button_enabled' not in st.session_state: st.session_state.graph_button_enabled = False
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0

with st.sidebar:
    st.header("⚙️ 보기 옵션")
    if st.session_state.processed_profiles:
        profile_names_sidebar = list(st.session_state.processed_profiles.keys())
        st.session_state.selected_profiles = st.multiselect("그래프에 표시할 프로파일 선택", options=profile_names_sidebar, default=profile_names_sidebar)
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
        st.subheader("온도 데이터 입력")
        main_input_method = st.radio("입력 방식", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        sub_input_method = st.radio("입력 방법", ("기본", "엑셀 데이터 붙여넣기"), key=f"sub_input_{current_name}", horizontal=True)
        if main_input_method == "구간 입력" and sub_input_method == "기본":
             st.info("구간(초): 현재 포인트에서 다음 포인트까지 걸릴 시간")
        
        column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "분": st.column_config.NumberColumn("분", disabled=(main_input_method == "구간 입력")), "초": st.column_config.NumberColumn("초", disabled=(main_input_method == "구간 입력")), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)", disabled=(main_input_method == "시간 입력")), "누적 시간 (초)": st.column_config.NumberColumn("누적 시간(초)", disabled=True), "ROR (℃/sec)": st.column_config.NumberColumn("ROR", format="%.3f", disabled=True)}
        default_visible_cols = ["Point", "온도"]
        if main_input_method == "시간 입력": default_visible_cols += ["분", "초"]
        else: default_visible_cols += ["구간 시간 (초)"]

        edited_df = st.session_state.profiles[current_name]
        text_area_content = ""
        if sub_input_method == "엑셀 데이터 붙여넣기":
            placeholder = "120 0 0\n..." if main_input_method == "시간 입력" else "120 40\n..."
            text_area_content = st.text_area("엑셀 데이터 붙여넣기", height=250, placeholder=placeholder, key=f"textarea_{current_name}", label_visibility="collapsed")
        else:
            df_editor_key = f"editor_{main_input_method}_{current_name}"
            edited_df = st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=df_editor_key, hide_index=True, num_rows="dynamic", column_order=default_visible_cols)
        
        if st.button("🔄 온도 데이터 동기화", key=f"sync_button_{current_name}"):
            profile_df_to_sync = None
            if sub_input_method == "기본": profile_df_to_sync = edited_df
            elif sub_input_method == "엑셀 데이터 붙여넣기" and text_area_content:
                parsed_df = parse_excel_data(text_area_content, main_input_method); profile_df_to_sync = create_new_profile(); profile_df_to_sync.update(parsed_df)
            if profile_df_to_sync is not None:
                synced_df = sync_profile_data(profile_df_to_sync, main_input_method); st.session_state.profiles[current_name] = synced_df; st.session_state.graph_button_enabled = True; st.rerun()

        with st.expander("팬 데이터 입력 (선택 사항)"):
            st.info("시간(분/초)에 따른 팬 속도(%)를 입력합니다.")
            fan_df = st.session_state.fan_profiles.get(current_name, create_new_fan_profile())
            fan_edited_df = st.data_editor(fan_df, column_config={"Point": st.column_config.NumberColumn("번호", disabled=True), "Fan (%)": st.column_config.NumberColumn("팬(%)", min_value=0, max_value=100), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "누적 시간 (초)": st.column_config.NumberColumn("누적(초)", disabled=True)}, num_rows="dynamic", key=f"fan_editor_{current_name}", hide_index=True)
            if st.button("🔄 팬 데이터 동기화", key=f"fan_sync_button_{current_name}"):
                synced_fan_df = sync_fan_data(fan_edited_df)
                st.session_state.fan_profiles[current_name] = synced_fan_df
                st.rerun()
st.divider()

st.header("📈 그래프 및 분석")
# (그래프 및 분석 패널 UI - 아직 팬 그래프는 추가되지 않음, 이전과 동일)
if st.button("📊 그래프 업데이트", disabled=not st.session_state.graph_button_enabled):
    st.session_state.processed_profiles = {name: calculate_ror(df.copy()) for name, df in st.session_state.profiles.items()}
    st.session_state.selected_time = 0
if st.session_state.processed_profiles:
    # (이하 코드 생략)
    pass
