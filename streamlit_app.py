import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- Helper function to assign teams (이전과 거의 동일, 인덱스 기반) ---
def assign_teams(df_original, cutoff_date_dt, num_target_teams):
    df_processed = df_original.copy()
    COL_JOIN_DATE_INTERNAL = '가입일' # 코드 내부에서 사용하는 가입일 컬럼명

    # '가입일' 컬럼 유효성 검사 및 변환
    if COL_JOIN_DATE_INTERNAL not in df_processed.columns:
        st.error(f"🚨 필수 컬럼 '{COL_JOIN_DATE_INTERNAL}'이 업로드된 파일에 없습니다. 컬럼명을 확인해주세요.")
        return None
    
    if not pd.api.types.is_datetime64_any_dtype(df_processed[COL_JOIN_DATE_INTERNAL]):
        try:
            df_processed[COL_JOIN_DATE_INTERNAL] = pd.to_datetime(df_processed[COL_JOIN_DATE_INTERNAL], errors='coerce')
        except Exception as e:
            st.error(f"'{COL_JOIN_DATE_INTERNAL}' 컬럼을 날짜 형식으로 변환 중 오류 발생: {e}")
            return None

    if df_processed[COL_JOIN_DATE_INTERNAL].isnull().any():
        st.warning(f"⚠️ '{COL_JOIN_DATE_INTERNAL}' 컬럼에 날짜로 변환할 수 없거나 비어있는 값이 있습니다. 해당 인원은 '기존 인원'으로 간주될 수 있습니다.")

    # 멤버 인덱스 기반으로 기존/신규 분리 (동명이인 문제 내부적 회피)
    all_original_indices = df_processed.index.tolist()
    existing_member_indices = []
    new_member_indices = []

    for original_idx in all_original_indices:
        member_join_date = df_processed.loc[original_idx, COL_JOIN_DATE_INTERNAL]
        if pd.isna(member_join_date) or member_join_date <= cutoff_date_dt:
            existing_member_indices.append(original_idx)
        else:
            new_member_indices.append(original_idx)
    
    np.random.seed(42); np.random.shuffle(existing_member_indices) # 재현성을 위한 시드
    np.random.seed(24); np.random.shuffle(new_member_indices)

    st.write(f"총 인원: {len(df_processed)}, 기존 인원 (우선 배정): {len(existing_member_indices)}, 신규 인원 (추가 배정): {len(new_member_indices)}")

    if num_target_teams <= 0:
        st.error("조 개수는 1 이상이어야 합니다."); return None

    member_to_new_team = {} # {original_df_index: team_name}
    teams_composition = {f"새로운 조 {i+1}": [] for i in range(num_target_teams)}
    
    # 1. 기존 멤버 배정 (Round-robin)
    for i, original_idx in enumerate(existing_member_indices):
        team_idx_for_member = i % num_target_teams
        assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name

    # 2. 신규 멤버 배정 (가장 작은 팀에 우선 배정)
    new_member_assignment_counter = 0 # 모든 멤버가 신규일 경우를 위한 카운터
    for original_idx in new_member_indices:
        team_sizes = {name: len(members_indices) for name, members_indices in teams_composition.items()}
        
        # 기존 멤버가 없거나, 아직 팀이 하나도 구성되지 않은 초기 상태 (모두 신규 멤버인 경우)
        if not existing_member_indices and not any(teams_composition.values()):
            team_idx_for_member = new_member_assignment_counter % num_target_teams
            assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
            new_member_assignment_counter += 1
        elif not team_sizes: # 극단적으로 팀 구성이 안된 경우 (로직상 거의 발생 안함)
             assigned_team_name = f"새로운 조 1" # 안전장치로 첫 번째 조에 배정
        else:
            # 인원수가 가장 적은 팀 찾기 (동점 시 이름순 첫 번째)
            smallest_team_name = min(team_sizes.items(), key=lambda x: (x[1], x[0]))[0]
            assigned_team_name = smallest_team_name
        
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name
        
    # 결과 DataFrame에 '새로운 조' 컬럼 추가
    df_result = df_original.copy()
    df_result['새로운 조'] = df_result.index.map(member_to_new_team)
    return df_result
# --- End of assign_teams function ---

# --- 조건부 서식 함수 ---
def highlight_team_changes(row, current_team_col_name, new_team_col_name):
    style = [''] * len(row) # 기본 스타일은 없음
    current_team_val = row.get(current_team_col_name)
    new_team_val = row.get(new_team_col_name)

    # '현재조'와 '새로운 조'가 모두 유효한 값이고, 서로 다를 때
    if pd.notna(current_team_val) and pd.notna(new_team_val) and current_team_val != new_team_val:
        try:
            # '새로운 조' 컬럼 위치에 배경색 적용
            new_team_idx = row.index.get_loc(new_team_col_name)
            style[new_team_idx] = 'background-color: yellow; font-weight: bold;'
            # '현재조' 컬럼 위치에도 다른 스타일 적용 가능
            current_team_idx = row.index.get_loc(current_team_col_name)
            style[current_team_idx] = 'text-decoration: line-through; color: grey;'

        except KeyError: # 컬럼이 없는 경우 예외 처리
            pass
    return style

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🌟 AI 조 배정 도우미 v2.0 🌟")
st.markdown("---")

# --- 앱에서 사용할 주요 컬럼명 정의 (사용자가 자신의 Excel 파일에 맞게 확인/수정 필요) ---
COL_NAME_APP = '이름'
COL_JOIN_DATE_APP = '가입일'  # 필수
COL_CURRENT_TEAM_APP = '현재조' # 기존 조를 나타내는 컬럼
COL_AGE_APP = '나이'
COL_PARTICIPATION_APP = '참석률 (한달 기준)'
# 요약에 사용할 범주형 특성 컬럼들
CATEGORICAL_FEATURES_APP = ['성별', '지역', '성경지식', '성향', '조원들과의 관계', '온/오프라인 참여', '거듭남']

# --- 사이드바: 입력 및 설정 ---
st.sidebar.header("⚙️ 조 배정 설정")
uploaded_file = st.sidebar.file_uploader("1. 명단 Excel 파일 업로드", type=["xlsx", "xls", "csv"])

# --- 안내 문구 ---
with st.expander("ℹ️ 사용 방법 및 중요 안내", expanded=False):
    st.markdown(f"""
    1.  **왼쪽 사이드바에서 Excel 또는 CSV 파일을 업로드 해주세요.**
        - **필수 컬럼**:
            - `{COL_NAME_APP}`: 이름 또는 식별자
            - `{COL_JOIN_DATE_APP}`: 가입일 (예: `2023-10-25` 또는 `10/25/2023` 형식 권장)
        - **기존 조 컬럼명**:
            - 현재 `{COL_CURRENT_TEAM_APP}`으로 설정되어 있습니다. **실제 파일의 컬럼명이 다르면 코드 상단을 직접 수정하거나, 아래 파일 컬럼명 매핑 기능을 이용하세요.**
        - **동명이인 주의**: 이 프로그램은 내부적으로는 멤버를 구분하지만, 결과 확인 시 혼란을 줄이려면 **각 멤버를 고유하게 식별할 수 있는 ID 컬럼을 추가**하고, `{COL_NAME_APP}` 대신 해당 ID 컬럼명을 사용하는 것이 가장 좋습니다.
    2.  **신규 인원 기준 날짜와 새로운 조의 총 개수를 설정합니다.**
    3.  **'새로운 조 배정 시작!' 버튼을 클릭합니다.**
    ---
    **참고**: 위에 명시된 컬럼명(`{COL_AGE_APP}`, `{COL_PARTICIPATION_APP}` 등)과 실제 파일의 컬럼명이 다를 경우, 해당 컬럼은 요약 정보에 포함되지 않거나 오류가 발생할 수 있습니다.
    """)
st.markdown("---")


if uploaded_file:
    try:
        # 파일 확장자에 따라 다르게 읽기
        if uploaded_file.name.endswith('.csv'):
            df_input_original = pd.read_csv(uploaded_file)
        else:
            df_input_original = pd.read_excel(uploaded_file)
        
        df_input = df_input_original.copy() # 원본 데이터프레임의 복사본으로 작업

        st.success("✅ 파일이 성공적으로 업로드되었습니다!")
        
        with st.expander("📄 업로드된 데이터 미리보기 (상위 5행)", expanded=False):
            st.dataframe(df_input.head())

        # --- 컬럼명 매핑 (선택적 기능) ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("컬럼명 매핑 (선택)")
        st.sidebar.caption("파일의 컬럼명이 코드 기본값과 다를 경우 여기서 지정하세요.")
        
        available_cols = ["코드 기본값 사용"] + list(df_input.columns)
        
        # 사용자가 컬럼명을 직접 선택할 수 있도록 개선 (COL_NAME_APP, COL_JOIN_DATE_APP, COL_CURRENT_TEAM_APP)
        # 선택된 컬럼명을 실제 앱 내부 변수에 할당
        # 이 부분은 코드를 더 복잡하게 만들 수 있으므로, 지금은 주석 처리하고 사용자에게 코드 상단 수정을 안내합니다.
        # name_col_selected = st.sidebar.selectbox(f"'{COL_NAME_APP}'에 해당하는 컬럼:", available_cols, index=available_cols.index(COL_NAME_APP) if COL_NAME_APP in available_cols else 0)
        # if name_col_selected != "코드 기본값 사용": COL_NAME_APP_USER = name_col_selected else: COL_NAME_APP_USER = COL_NAME_APP
        # (이런 식으로 모든 주요 컬럼에 대해 반복)
        # 여기서는 단순화를 위해 코드 상단 수정 방식을 유지합니다.
        
        # 필수 컬럼 존재 여부 확인
        required_cols_in_app = [COL_NAME_APP, COL_JOIN_DATE_APP]
        missing_cols = [col for col in required_cols_in_app if col not in df_input.columns]
        if missing_cols:
            st.error(f"🚨 필수 컬럼 누락: **{', '.join(missing_cols)}** 이(가) 파일에 없습니다. 컬럼명을 확인하거나 파일을 수정해주세요. (코드 상단 또는 파일 내 컬럼명 확인)")
            st.stop()
        
        # '현재조' 컬럼 존재 여부 확인 (선택 사항)
        if COL_CURRENT_TEAM_APP not in df_input.columns:
            st.warning(f"⚠️ '현재조' 컬럼(`{COL_CURRENT_TEAM_APP}`)을 파일에서 찾을 수 없습니다. '현재조' 정보 없이 새로운 조만 표시됩니다.")
            df_input[COL_CURRENT_TEAM_APP] = None # 없는 경우 None으로 채워 조건부 서식 등에서 오류 방지


        # --- 사용자 입력 (사이드바) ---
        default_cutoff_date = datetime.now().date()
        valid_join_dates = pd.to_datetime(df_input[COL_JOIN_DATE_APP], errors='coerce').dropna()
        if not valid_join_dates.empty:
            default_cutoff_date = valid_join_dates.quantile(0.75).date() 
        
        cutoff_date_input = st.sidebar.date_input(f"2. 신규 인원 기준 날짜", 
                                    value=default_cutoff_date,
                                    help=f"이 날짜 **이후** '{COL_JOIN_DATE_APP}' 컬럼의 날짜를 가진 사람이 신규로 분류됩니다.")
        
        default_num_teams = 3 
        if COL_CURRENT_TEAM_APP in df_input.columns and df_input[COL_CURRENT_TEAM_APP].notna().any():
            unique_current_teams = df_input[COL_CURRENT_TEAM_APP].dropna().nunique()
            if unique_current_teams > 0:
                default_num_teams = unique_current_teams
        
        num_target_teams_input = st.sidebar.number_input("3. 배정할 새로운 조의 총 개수:", 
                                           min_value=1, 
                                           value=int(default_num_teams),
                                           step=1)

        if st.sidebar.button("🚀 새로운 조 배정 시작!", type="primary", use_container_width=True):
            if cutoff_date_input:
                cutoff_date_dt_input = pd.to_datetime(cutoff_date_input)
                
                st.markdown("---")
                st.subheader("⏳ 조 배정 진행 결과")
                
                with st.spinner("데이터를 분석하고 조를 배정하고 있습니다..."):
                    df_result = assign_teams(df_input, cutoff_date_dt_input, num_target_teams_input) 
                
                if df_result is not None:
                    st.success("🎉 새로운 조 배정이 완료되었습니다!")
                    
                    # --- 결과 테이블 표시 (주요 정보 앞쪽, 조건부 서식 적용) ---
                    st.markdown("#### 📋 **조 배정 결과표**")
                    st.caption(f"'{COL_CURRENT_TEAM_APP}'에서 '새로운 조'로 변경된 경우 노란색으로 강조 표시됩니다.")

                    cols_to_show_first = [COL_NAME_APP]
                    # COL_CURRENT_TEAM_APP이 실제 df_result에 있는지 확인 후 추가
                    if COL_CURRENT_TEAM_APP in df_result.columns:
                        cols_to_show_first.append(COL_CURRENT_TEAM_APP)
                    else: # 없으면 새로 생성해서라도 컬럼 순서 유지 (highlight 함수에서 오류 안나게)
                        df_result[COL_CURRENT_TEAM_APP] = None
                        cols_to_show_first.append(COL_CURRENT_TEAM_APP)


                    cols_to_show_first.extend(['새로운 조', COL_JOIN_DATE_APP])
                    
                    remaining_cols = [col for col in df_result.columns if col not in cols_to_show_first]
                    ordered_cols = cols_to_show_first + remaining_cols
                    
                    # 조건부 서식을 위한 Styler 객체 생성
                    df_styled = df_result[ordered_cols].style.apply(
                        highlight_team_changes, 
                        axis=1, 
                        current_team_col_name=COL_CURRENT_TEAM_APP, 
                        new_team_col_name='새로운 조'
                    )
                    st.dataframe(df_styled)


                    # --- 조별 인원수 시각화 ---
                    st.markdown("#### 📊 **새로운 조별 인원수**")
                    if '새로운 조' in df_result.columns and df_result['새로운 조'].notna().any():
                        team_counts = df_result['새로운 조'].value_counts().sort_index()
                        st.bar_chart(team_counts)
                    else:
                        st.info("배정된 조가 없어 인원수 차트를 표시할 수 없습니다.")

                    # --- 조별 상세 요약 (이전과 유사, Expander 사용) ---
                    st.markdown("---")
                    st.subheader("ℹ️ 새로운 조별 상세 요약")
                    
                    if '새로운 조' in df_result.columns and not df_result['새로운 조'].isnull().all():
                        grouped_results = df_result.dropna(subset=['새로운 조']).groupby('새로운 조')
                        
                        for team_name_summary, group_df_summary in grouped_results:
                            summary_items = {'인원수': len(group_df_summary)}
                            
                            # 기존 조 구성원 분포
                            if COL_CURRENT_TEAM_APP in group_df_summary.columns and group_df_summary[COL_CURRENT_TEAM_APP].notna().any():
                                current_team_counts = group_df_summary[COL_CURRENT_TEAM_APP].value_counts().to_dict()
                                summary_items[f'`{COL_CURRENT_TEAM_APP}` 출신'] = ', '.join([f"{k}({v})" for k,v in current_team_counts.items()]) if current_team_counts else '정보 없음'
                            
                            # 수치형 데이터 요약
                            if COL_AGE_APP in group_df_summary.columns and pd.api.types.is_numeric_dtype(group_df_summary[COL_AGE_APP]):
                                summary_items[f'평균 `{COL_AGE_APP}`'] = round(group_df_summary[COL_AGE_APP].mean(skipna=True), 1) if not group_df_summary[COL_AGE_APP].isnull().all() else 'N/A'
                            if COL_PARTICIPATION_APP in group_df_summary.columns and pd.api.types.is_numeric_dtype(group_df_summary[COL_PARTICIPATION_APP]):
                                summary_items[f'평균 `{COL_PARTICIPATION_APP}`'] = round(group_df_summary[COL_PARTICIPATION_APP].mean(skipna=True), 2) if not group_df_summary[COL_PARTICIPATION_APP].isnull().all() else 'N/A'
                            
                            # 범주형 데이터 요약
                            for cat_col_name_summary in CATEGORICAL_FEATURES_APP:
                                if cat_col_name_summary in group_df_summary.columns:
                                    counts = group_df_summary[cat_col_name_summary].astype(str).value_counts(dropna=False).to_dict()
                                    filtered_counts = {k: v for k, v in counts.items() if k.lower() not in ['nan', 'none','nat', '정보 없음',str(None)]}
                                    summary_items[f'`{cat_col_name_summary}` 분포'] = ', '.join([f"{k}({v})" for k,v in filtered_counts.items()]) if filtered_counts else '데이터 없음'
                            
                            with st.expander(f"**{team_name_summary}** (총 {summary_items['인원수']}명)", expanded=True):
                                for key, value in summary_items.items():
                                    if key != '인원수': 
                                        st.markdown(f"- **{key}**: {value if pd.notna(value) and value else 'N/A'}")
                        
                        # 결과 다운로드 버튼
                        @st.cache_data
                        def convert_df_to_csv(df_to_convert):
                            return df_to_convert.to_csv(index=False).encode('utf-8-sig')

                        csv_output = convert_df_to_csv(df_result[ordered_cols])
                        st.sidebar.markdown("---") # 다운로드 버튼도 사이드바로 이동
                        st.sidebar.download_button(
                            label="💾 결과 CSV 파일로 다운로드",
                            data=csv_output,
                            file_name=f"새로운_조_배정_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.warning("⚠️ 새로운 조가 배정되지 않았거나, '새로운 조' 컬럼이 결과에 없습니다.")
            else:
                st.sidebar.error("🚨 신규 인원 기준 날짜를 선택해주세요.")

    except pd.errors.ParserError:
        st.error("🚨 Excel/CSV 파일 파싱 오류: 파일 형식이 손상되었거나 지원하지 않는 형식일 수 있습니다.")
    except ValueError as ve:
        st.error(f"🚨 데이터 처리 중 값 오류 발생: {ve} (컬럼명 또는 데이터 타입을 확인해주세요)")
    except Exception as e:
        st.error(f"🚨 예기치 않은 오류 발생: {e}")
        st.error("업로드한 파일의 내용과 형식을 다시 한번 확인해주세요. 문제가 지속되면 개발자에게 문의하세요.")
else:
    st.sidebar.info("☝️ 시작하려면 여기에 Excel 또는 CSV 파일을 업로드해주세요.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>Streamlit 조 배정 도우미</p>", unsafe_allow_html=True)
