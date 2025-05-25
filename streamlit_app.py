import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- Helper function to assign teams (이전과 동일) ---
def assign_teams(df_original, cutoff_date_dt, num_target_teams):
    df_processed = df_original.copy() 
    COL_JOIN_DATE_INTERNAL = '가입일' 

    if COL_JOIN_DATE_INTERNAL not in df_processed.columns:
        st.error(f"필수 컬럼 '{COL_JOIN_DATE_INTERNAL}'이 업로드된 파일에 없습니다.")
        return None
    
    if not pd.api.types.is_datetime64_any_dtype(df_processed[COL_JOIN_DATE_INTERNAL]):
        try:
            df_processed[COL_JOIN_DATE_INTERNAL] = pd.to_datetime(df_processed[COL_JOIN_DATE_INTERNAL], errors='coerce')
        except Exception as e:
            st.error(f"'{COL_JOIN_DATE_INTERNAL}' 컬럼 변환 오류: {e}")
            return None

    if df_processed[COL_JOIN_DATE_INTERNAL].isnull().any():
        st.warning(f"'{COL_JOIN_DATE_INTERNAL}'에 날짜 변환 불가/빈 값이 있습니다. 해당 인원은 '기존 인원'으로 간주될 수 있습니다.")

    all_original_indices = df_processed.index.tolist()
    existing_member_indices = []
    new_member_indices = []

    for original_idx in all_original_indices:
        member_join_date = df_processed.loc[original_idx, COL_JOIN_DATE_INTERNAL]
        if pd.isna(member_join_date) or member_join_date <= cutoff_date_dt:
            existing_member_indices.append(original_idx)
        else:
            new_member_indices.append(original_idx)
    
    np.random.seed(42); np.random.shuffle(existing_member_indices)
    np.random.seed(24); np.random.shuffle(new_member_indices)

    st.write(f"총 인원: {len(df_processed)}, 기존 인원 (배정 대상): {len(existing_member_indices)}, 신규 인원 (배정 대상): {len(new_member_indices)}")

    if num_target_teams <= 0:
        st.error("조 개수는 1 이상이어야 합니다."); return None

    member_to_new_team = {} 
    teams_composition = {f"새로운 조 {i+1}": [] for i in range(num_target_teams)}
    
    for i, original_idx in enumerate(existing_member_indices):
        team_idx_for_member = i % num_target_teams
        assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name

    new_member_assignment_counter = 0
    for original_idx in new_member_indices:
        team_sizes = {name: len(members_indices) for name, members_indices in teams_composition.items()}
        if not existing_member_indices and not any(teams_composition.values()): # 기존 멤버 없고, 팀 구성도 아직 안된 경우 (모두 신규)
            team_idx_for_member = new_member_assignment_counter % num_target_teams
            assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
            new_member_assignment_counter +=1
        elif not team_sizes: # 팀 구성이 아직 안된 극단적 경우 대비
             assigned_team_name = f"새로운 조 1" # 일단 첫번째 조에 배정
        else:
            smallest_team_name = min(team_sizes.items(), key=lambda x: (x[1], x[0]))[0]
            assigned_team_name = smallest_team_name
        
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name
        
    df_result = df_original.copy()
    df_result['새로운 조'] = df_result.index.map(member_to_new_team)
    return df_result
# --- End of assign_teams function ---


# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🌟 AI 조 배정 도우미 🌟")
st.markdown("---")

# --- 앱에서 사용할 주요 컬럼명 정의 ---
# 사용자의 Excel 파일의 실제 컬럼명과 일치하도록 수정 필요
COL_NAME_APP = '이름'
COL_JOIN_DATE_APP = '가입일'  # 필수
COL_CURRENT_TEAM_APP = '현재조' # 기존 조를 나타내는 컬럼 (없으면 None 또는 다른 이름으로)
COL_AGE_APP = '나이'
COL_PARTICIPATION_APP = '참석률 (한달 기준)'
# 요약에 사용할 범주형 특성 컬럼들 (사용자 데이터에 따라 추가/수정)
CATEGORICAL_FEATURES_APP = ['성별', '지역', '성경지식', '성향', '조원들과의 관계', '온/오프라인 참여', '거듭남']
# (주의: COL_CURRENT_TEAM_APP도 여기에 포함될 수 있지만, 요약에서는 특별히 다룰 수 있음)

# --- 안내 문구 ---
st.markdown("""
안녕하세요! 이 도구는 Excel 명단을 기반으로 새로운 조를 배정해 드립니다.
몇 가지 정보를 입력하고 파일을 업로드해주세요.
""")

with st.expander("ℹ️ 사용 방법 및 컬럼 안내", expanded=False):
    st.markdown(f"""
    - **파일 형식**: Excel (`.xlsx`, `.xls`)
    - **필수 컬럼**:
        - `{COL_NAME_APP}`: 각 인원의 이름 또는 고유 식별자
        - `{COL_JOIN_DATE_APP}`: 가입일 (예: `2023-10-25` 형식 권장)
    - **기존 조 컬럼명 (중요!)**:
        - 코드에 `{COL_CURRENT_TEAM_APP}`으로 설정되어 있습니다. **만약 실제 파일의 컬럼명이 다르면, 코드 상단을 수정해주세요.** (예: '기존팀', '소속조' 등)
        - 이 컬럼이 파일에 없어도 작동은 하지만, '현재조' 대비 '새로운 조' 비교가 어렵습니다.
    - **활용 컬럼 예시 (요약 정보에 사용)**:
        - `{COL_AGE_APP}`, `{COL_PARTICIPATION_APP}` (숫자 형식)
        - `{', '.join(CATEGORICAL_FEATURES_APP)}` 등 (범주형 데이터)
    - **신규 인원 기준**: 입력하신 날짜 **이후** `{COL_JOIN_DATE_APP}`을 가진 사람은 신규 인원으로 분류됩니다.
    - **조 배정 로직**:
        1.  **기존 인원**: 무작위로 섞어 지정된 조 개수에 최대한 균등하게 배정합니다 (Round-robin).
        2.  **신규 인원**: 기존 인원으로 구성된 조 중 현재 인원수가 가장 적은 조에 우선 배정됩니다. (모든 인원이 신규일 경우, 신규 인원도 Round-robin으로 배정)
    """)
st.markdown("---")

# --- 입력 섹션 ---
st.sidebar.header("⚙️ 조 배정 설정")
uploaded_file = st.sidebar.file_uploader("1. 명단 Excel 파일 업로드", type=["xlsx", "xls"])

if uploaded_file:
    try:
        df_input_original = pd.read_excel(uploaded_file) 
        df_input = df_input_original.copy()

        st.success("✅ 파일이 성공적으로 업로드되었습니다!")
        
        with st.expander("📄 업로드된 데이터 미리보기 (상위 5행)", expanded=False):
            st.dataframe(df_input.head())

        # 필수 컬럼 존재 여부 확인
        required_cols_in_app = [COL_NAME_APP, COL_JOIN_DATE_APP]
        missing_cols = [col for col in required_cols_in_app if col not in df_input.columns]
        if missing_cols:
            st.error(f"🚨 필수 컬럼 누락: **{', '.join(missing_cols)}** 이(가) 파일에 없습니다. 컬럼명을 확인하거나 파일을 수정해주세요.")
            st.stop() # 오류 시 진행 중단
        
        # '현재조' 컬럼 존재 여부 확인 및 안내 (에러는 아님)
        if COL_CURRENT_TEAM_APP not in df_input.columns:
            st.warning(f"⚠️ '현재조' 컬럼(`{COL_CURRENT_TEAM_APP}`)을 파일에서 찾을 수 없습니다. 새로운 조만 표시됩니다.")
            # '현재조' 컬럼이 없으면 빈 값으로 채워넣어 이후 로직 에러 방지
            df_input[COL_CURRENT_TEAM_APP] = "정보 없음" 


        # --- 사용자 입력 ---
        default_cutoff_date = datetime.now().date()
        valid_join_dates = pd.to_datetime(df_input[COL_JOIN_DATE_APP], errors='coerce').dropna()
        if not valid_join_dates.empty:
            # 데이터 중간값 또는 80% 지점 등으로 기본값 설정 가능
            default_cutoff_date = valid_join_dates.quantile(0.75).date() 
        
        cutoff_date_input = st.sidebar.date_input(f"2. 신규 인원 기준 날짜", 
                                    value=default_cutoff_date,
                                    help=f"이 날짜 **이후** '{COL_JOIN_DATE_APP}' 컬럼의 날짜를 가진 사람이 신규 인원으로 분류됩니다.")
        
        default_num_teams = 3 
        if COL_CURRENT_TEAM_APP in df_input.columns: # '현재조' 컬럼이 있을 때만 사용
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
                st.subheader("⏳ 조 배정 진행 중...")
                progress_bar = st.progress(0)
                
                with st.spinner("데이터를 분석하고 조를 배정하고 있습니다..."):
                    df_result = assign_teams(df_input, cutoff_date_dt_input, num_target_teams_input) 
                    progress_bar.progress(100)
                
                if df_result is not None:
                    st.subheader("🎉 새로운 조 배정 완료!")
                    
                    # 결과 테이블 컬럼 순서 조정 (주요 정보 먼저)
                    cols_to_show_first = [COL_NAME_APP]
                    if COL_CURRENT_TEAM_APP in df_result.columns:
                        cols_to_show_first.append(COL_CURRENT_TEAM_APP)
                    cols_to_show_first.extend(['새로운 조', COL_JOIN_DATE_APP])
                    
                    remaining_cols = [col for col in df_result.columns if col not in cols_to_show_first]
                    ordered_cols = cols_to_show_first + remaining_cols
                    
                    st.dataframe(df_result[ordered_cols])

                    st.markdown("---")
                    st.subheader("📊 새로운 조별 상세 요약")
                    
                    if '새로운 조' in df_result.columns and not df_result['새로운 조'].isnull().all():
                        grouped_results = df_result.dropna(subset=['새로운 조']).groupby('새로운 조')
                        
                        for team_name, group_df in grouped_results:
                            team_summary = {'인원수': len(group_df)}
                            
                            # 기존 조 구성원 분포
                            if COL_CURRENT_TEAM_APP in group_df.columns:
                                current_team_counts = group_df[COL_CURRENT_TEAM_APP].value_counts().to_dict()
                                team_summary[f'{COL_CURRENT_TEAM_APP} 출신 분포'] = ', '.join([f"{k}({v})" for k,v in current_team_counts.items()]) if current_team_counts else '정보 없음'
                            
                            # 수치형 데이터 요약
                            if COL_AGE_APP in group_df.columns and pd.api.types.is_numeric_dtype(group_df[COL_AGE_APP]):
                                team_summary[f'평균 {COL_AGE_APP}'] = round(group_df[COL_AGE_APP].mean(skipna=True), 1) if not group_df[COL_AGE_APP].isnull().all() else 'N/A'
                            if COL_PARTICIPATION_APP in group_df.columns and pd.api.types.is_numeric_dtype(group_df[COL_PARTICIPATION_APP]):
                                team_summary[f'평균 {COL_PARTICIPATION_APP}'] = round(group_df[COL_PARTICIPATION_APP].mean(skipna=True), 2) if not group_df[COL_PARTICIPATION_APP].isnull().all() else 'N/A'
                            
                            # 범주형 데이터 요약
                            for cat_col_name in CATEGORICAL_FEATURES_APP:
                                if cat_col_name in group_df.columns:
                                    counts = group_df[cat_col_name].astype(str).value_counts(dropna=False).to_dict()
                                    filtered_counts = {k: v for k, v in counts.items() if k.lower() not in ['nan', 'none','nat', '정보 없음']} # '정보 없음'도 제외
                                    team_summary[f'{cat_col_name} 분포'] = ', '.join([f"{k}({v})" for k,v in filtered_counts.items()]) if filtered_counts else '데이터 없음'
                            
                            # Expander로 조별 정보 표시
                            with st.expander(f"**{team_name}** (총 {team_summary['인원수']}명)", expanded=True):
                                for key, value in team_summary.items():
                                    if key != '인원수': # 인원수는 이미 expander 제목에 있음
                                        st.markdown(f"- **{key.replace(' 분포', '')}**: {value if value else 'N/A'}")
                        
                        # 결과 다운로드 버튼
                        @st.cache_data
                        def convert_df_to_csv(df_to_convert):
                            return df_to_convert.to_csv(index=False).encode('utf-8-sig')

                        csv_output = convert_df_to_csv(df_result[ordered_cols]) # 정렬된 컬럼 순서대로 다운로드
                        st.download_button(
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
        st.error("🚨 Excel 파일 파싱 오류: 파일 형식이 손상되었거나 지원하지 않는 Excel 버전일 수 있습니다.")
    except ValueError as ve:
        st.error(f"🚨 데이터 처리 중 값 오류 발생: {ve}")
    except Exception as e:
        st.error(f"🚨 예기치 않은 오류 발생: {e}")
        st.error("업로드한 Excel 파일의 내용과 형식을 다시 한번 확인해주세요. 문제가 지속되면 개발자에게 문의하세요.")
else:
    st.sidebar.info("☝️ 시작하려면 여기에 Excel 파일을 업로드해주세요.")

st.markdown("---")
st.markdown("<p style='text-align: center;'>Made with ❤️ and Streamlit</p>", unsafe_allow_html=True)
