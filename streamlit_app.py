import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Helper function to assign teams
def assign_teams(df_original, cutoff_date_dt, num_target_teams):
    df_processed = df_original.copy() # 원본 데이터프레임 복사해서 사용

    # 사용할 컬럼명 (사용자 Excel 파일의 실제 컬럼명과 일치해야 함)
    COL_JOIN_DATE_INTERNAL = '가입일' 

    # '가입일' 컬럼을 datetime으로 변환 (필수)
    if COL_JOIN_DATE_INTERNAL not in df_processed.columns:
        st.error(f"필수 컬럼 '{COL_JOIN_DATE_INTERNAL}'이 업로드된 파일에 없습니다. 컬럼명을 확인해주세요.")
        return None
    
    if not pd.api.types.is_datetime64_any_dtype(df_processed[COL_JOIN_DATE_INTERNAL]):
        try:
            df_processed[COL_JOIN_DATE_INTERNAL] = pd.to_datetime(df_processed[COL_JOIN_DATE_INTERNAL], errors='coerce')
        except Exception as e:
            st.error(f"'{COL_JOIN_DATE_INTERNAL}' 컬럼을 날짜 형식으로 변환 중 오류 발생: {e}")
            st.info(f"Excel에서 '{COL_JOIN_DATE_INTERNAL}' 컬럼 형식을 'YYYY-MM-DD' 또는 'MM/DD/YYYY' 등으로 확인해주세요.")
            return None

    if df_processed[COL_JOIN_DATE_INTERNAL].isnull().any():
        st.warning(f"'{COL_JOIN_DATE_INTERNAL}' 컬럼에 날짜로 변환할 수 없거나 비어있는 값이 있습니다. 해당 인원은 '기존 인원'으로 간주될 수 있습니다.")

    # 1. 기존 멤버와 신규 멤버의 원본 인덱스 분리 및 셔플
    all_original_indices = df_processed.index.tolist()

    existing_member_indices = []
    new_member_indices = []

    for original_idx in all_original_indices:
        member_join_date = df_processed.loc[original_idx, COL_JOIN_DATE_INTERNAL]
        
        # NaT (Not a Time)이거나 날짜가 cutoff_date_dt 이전이면 기존 멤버
        if pd.isna(member_join_date) or member_join_date <= cutoff_date_dt:
            existing_member_indices.append(original_idx)
        else: # 날짜가 cutoff_date_dt 이후면 신규 멤버
            new_member_indices.append(original_idx)
    
    # 재현성을 위해 셔플
    np.random.seed(42) # 기존 멤버 셔플용 시드
    np.random.shuffle(existing_member_indices)
    
    np.random.seed(24) # 신규 멤버 셔플용 시드 (다른 시드 사용 권장)
    np.random.shuffle(new_member_indices)

    st.write(f"총 인원: {len(df_processed)}, 기존 인원 (배정 대상): {len(existing_member_indices)}, 신규 인원 (배정 대상): {len(new_member_indices)}")

    if num_target_teams <= 0:
        st.error("조 개수는 1 이상이어야 합니다.")
        return None

    # member_to_new_team: {original_df_index: team_name}
    member_to_new_team = {} 
    # teams_composition: {team_name: [original_df_index, ...]}
    teams_composition = {f"새로운 조 {i+1}": [] for i in range(num_target_teams)}
    
    # 2. 기존 멤버 배정 (Round-robin)
    for i, original_idx in enumerate(existing_member_indices):
        team_idx_for_member = i % num_target_teams
        assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
        
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name

    # 3. 신규 멤버 배정 (가장 작은 팀에 우선 배정)
    # 신규 멤버 배정 시 사용할 인덱스 (기존 멤버 배정 후 이어서 카운트하기 위함)
    # 모든 멤버가 신규일 경우를 대비해 초기화
    new_member_assignment_counter = 0
    for original_idx in new_member_indices:
        # 현재 팀별 인원수 계산
        team_sizes = {name: len(members_indices) for name, members_indices in teams_composition.items()}
        
        if not existing_member_indices: # 모든 멤버가 신규이거나, 기존 멤버가 없는 경우
            # 신규 멤버도 Round-robin 방식으로 배정
            team_idx_for_member = new_member_assignment_counter % num_target_teams
            assigned_team_name = f"새로운 조 {team_idx_for_member + 1}"
            new_member_assignment_counter +=1
        else:
            # 가장 인원수가 적은 팀 찾기 (동점 시 이름순으로 첫 번째 팀 - 안정적인 배정)
            # (인원수, 팀이름) 튜플로 정렬하여 최소값 찾기
            smallest_team_name = min(team_sizes.items(), key=lambda x: (x[1], x[0]))[0]
            assigned_team_name = smallest_team_name
        
        teams_composition[assigned_team_name].append(original_idx)
        member_to_new_team[original_idx] = assigned_team_name
        
    # 4. 결과 DataFrame 생성
    df_result = df_original.copy()
    df_result['새로운 조'] = df_result.index.map(member_to_new_team)

    return df_result

# Streamlit App UI
st.set_page_config(layout="wide")
st.title("🧑‍🤝‍🧑 AI 조 배정 도우미 🤖 (Excel 컬럼 맞춤형)")

st.markdown("""
이 앱은 Excel 파일을 업로드 받아 새로운 조를 배정합니다.
- **파일 형식**: Excel (`.xlsx`, `.xls`)
- **필수 컬럼**: `이름`, `가입일` (날짜 형식: YYYY-MM-DD 또는 pandas가 인식 가능한 날짜 형식 권장)
- **활용 컬럼 예시**: `성별`, `지역`, `생년월일`, `나이`, `참석률 (한달 기준)`, `성경지식`, `성향`, `조원들과의 관계`, `온/오프라인 참여`, `거듭남`, `현재조` 등.
  (다른 컬럼이 더 있어도 괜찮습니다. 아래 요약 정보에 활용될 수 있습니다.)
- **신규 인원 기준**: 입력하신 날짜 이후 `가입일`을 가진 사람은 신규 인원으로 분류됩니다. (해당 날짜 포함하지 않음)
- **조 배정 로직**:
    1. **기존 인원**: 무작위로 섞어 지정된 조 개수에 최대한 균등하게 배정 (Round-robin 방식).
    2. **신규 인원**: 기존 인원으로 구성된 조 중 현재 인원수가 가장 적은 조에 우선 배정. (모든 인원이 신규이거나 기존 인원이 없는 경우, 신규 인원도 Round-robin 방식으로 배정)
""")

uploaded_file = st.file_uploader("조 편성할 명단 Excel 파일 업로드 (컬럼명 확인!)", type=["xlsx", "xls"])

# 앱에서 사용할 주요 컬럼명 정의 (사용자 Excel 파일의 실제 컬럼명과 일치해야 함)
# 이 부분은 사용자가 자신의 파일에 맞게 확인하거나, 추후 UI로 선택하게 할 수 있음
COL_NAME_APP = '이름'
COL_JOIN_DATE_APP = '가입일'
COL_AGE_APP = '나이' 
COL_PARTICIPATION_APP = '참석률 (한달 기준)' # 이미지의 '참석률 (한달 기준)'
# 범주형 특성 컬럼들 (사용자 데이터에 따라 추가/수정, 이미지 기반)
CATEGORICAL_FEATURES_APP = ['성별', '지역', '성경지식', '성향', '조원들과의 관계', '온/오프라인 참여', '거듭남', '현재조']


if uploaded_file:
    try:
        # 원본 데이터 로드 시, 특정 시트를 지정해야 할 경우 sheet_name 파라미터 사용
        df_input_original = pd.read_excel(uploaded_file) 
        df_input = df_input_original.copy() # 원본 DataFrame의 복사본으로 작업

        st.subheader("업로드된 데이터 일부 (상위 5행):")
        st.dataframe(df_input.head())

        # 필수 컬럼 존재 여부 확인
        required_cols_in_app = [COL_NAME_APP, COL_JOIN_DATE_APP]
        missing_cols = [col for col in required_cols_in_app if col not in df_input.columns]
        if missing_cols:
            st.error(f"필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")
            st.info(f"Excel 파일에 '{COL_NAME_APP}' 컬럼과 '{COL_JOIN_DATE_APP}' 컬럼이 있는지, 철자가 정확한지 확인해주세요.")
        else:
            # 날짜 형식 사전 확인 (실제 변환은 assign_teams 함수에서 수행)
            try:
                # errors='coerce'로 하면 경고 없이 NaT로 만드므로, 여기서는 raise로 오류 발생시켜 사용자에게 알림
                pd.to_datetime(df_input[COL_JOIN_DATE_APP], errors='raise') 
            except Exception:
                st.warning(f"'{COL_JOIN_DATE_APP}' 컬럼에 날짜로 인식할 수 없는 값이 포함되어 있을 수 있습니다. 'YYYY-MM-DD' 또는 'MM/DD/YYYY' 형식 등을 권장합니다. 문제가 있는 데이터는 조 편성 시 '기존 인원'으로 분류될 수 있습니다.")

            # 신규 인원 기준 날짜 입력
            default_cutoff_date = datetime.now().date()
            # '가입일' 데이터가 유효한 경우, 중간값을 기본 날짜로 제안
            valid_join_dates = pd.to_datetime(df_input[COL_JOIN_DATE_APP], errors='coerce').dropna()
            if not valid_join_dates.empty:
                default_cutoff_date = valid_join_dates.quantile(0.5).date() 
            
            cutoff_date_input = st.date_input(f"신규 인원 기준 날짜 (이 날짜 **이후** '{COL_JOIN_DATE_APP}' 컬럼의 날짜를 가진 사람 = 신규)", 
                                        value=default_cutoff_date,
                                        help=f"'{COL_JOIN_DATE_APP}'이 이 날짜보다 **큰** 경우 신규 인원으로 분류됩니다. (예: 기준일이 1월 1일이면, 1월 2일부터 신규)")
            
            # 원하는 조 개수 입력
            default_num_teams = 3 
            if '현재조' in df_input.columns: 
                unique_current_teams = df_input['현재조'].dropna().nunique()
                if unique_current_teams > 0:
                    default_num_teams = unique_current_teams
            
            num_target_teams_input = st.number_input("배정할 새로운 조의 총 개수:", 
                                               min_value=1, 
                                               value=int(default_num_teams),
                                               step=1)

            if st.button("🚀 새로운 조 배정 시작!"):
                if cutoff_date_input:
                    cutoff_date_dt_input = pd.to_datetime(cutoff_date_input) # datetime.date to datetime64
                    
                    with st.spinner("조를 배정 중입니다... 잠시만 기다려주세요."):
                        df_result = assign_teams(df_input, cutoff_date_dt_input, num_target_teams_input) 
                    
                    if df_result is not None:
                        st.subheader("🎉 새로운 조 배정 결과:")
                        st.dataframe(df_result)

                        st.subheader("📊 조별 요약:")
                        summary_list = []
                        if '새로운 조' in df_result.columns and not df_result['새로운 조'].isnull().all():
                            # '새로운 조'가 NaN인 경우(배정 실패 등)를 제외하고 그룹화
                            grouped_results = df_result.dropna(subset=['새로운 조']).groupby('새로운 조')
                            
                            for team_name, group_df in grouped_results:
                                team_summary = {'조 이름': team_name, '인원수': len(group_df)}
                                
                                # 수치형 데이터 요약 (나이, 참석률)
                                if COL_AGE_APP in group_df.columns and pd.api.types.is_numeric_dtype(group_df[COL_AGE_APP]):
                                    team_summary[f'평균 {COL_AGE_APP}'] = round(group_df[COL_AGE_APP].mean(skipna=True), 1) if not group_df[COL_AGE_APP].isnull().all() else 'N/A'
                                
                                if COL_PARTICIPATION_APP in group_df.columns and pd.api.types.is_numeric_dtype(group_df[COL_PARTICIPATION_APP]):
                                    team_summary[f'평균 {COL_PARTICIPATION_APP}'] = round(group_df[COL_PARTICIPATION_APP].mean(skipna=True), 2) if not group_df[COL_PARTICIPATION_APP].isnull().all() else 'N/A'
                                
                                # 범주형 데이터 요약 (CATEGORICAL_FEATURES_APP 리스트 사용)
                                for cat_col_name in CATEGORICAL_FEATURES_APP:
                                    if cat_col_name in group_df.columns:
                                        # NaN 값을 가진 행도 포함하여 value_counts 계산 후, NaN은 문자열 'nan'으로 표시됨
                                        counts = group_df[cat_col_name].astype(str).value_counts(dropna=False).to_dict()
                                        # 'nan' 또는 'None' 문자열로 표시된 결측치는 요약에서 제외하거나 별도 표시 가능
                                        filtered_counts = {k: v for k, v in counts.items() if k.lower() not in ['nan', 'none','nat']}
                                        if filtered_counts:
                                            team_summary[f'{cat_col_name} 분포'] = ', '.join([f"{k}({v})" for k,v in filtered_counts.items()])
                                        else:
                                            team_summary[f'{cat_col_name} 분포'] = 'N/A'
                                
                                summary_list.append(team_summary)
                            
                            if summary_list:
                                summary_df = pd.DataFrame(summary_list).set_index('조 이름') # 조 이름을 인덱스로
                                st.dataframe(summary_df)
                            else:
                                st.info("요약할 데이터가 없습니다. 배정된 조가 있는지 확인해주세요.")

                            # 결과 다운로드 버튼
                            @st.cache_data # Streamlit의 새로운 캐싱 데코레이터
                            def convert_df_to_csv(df_to_convert):
                                return df_to_convert.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지

                            csv_output = convert_df_to_csv(df_result)
                            st.download_button(
                                label="결과 CSV 파일로 다운로드",
                                data=csv_output,
                                file_name=f"새로운_조_배정_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.warning("새로운 조가 배정되지 않았거나, '새로운 조' 컬럼이 결과에 없습니다. 업로드한 파일과 설정을 확인해주세요.")
                else:
                    st.error("신규 인원 기준 날짜를 선택해주세요.")
    except pd.errors.ParserError:
        st.error("Excel 파일 파싱 오류: 파일 형식이 손상되었거나 지원하지 않는 Excel 버전일 수 있습니다. '.xlsx' 또는 깨끗한 '.xls' 파일을 확인해주세요.")
    except ValueError as ve:
        st.error(f"데이터 처리 중 값 오류 발생: {ve}")
        st.info("특히 날짜나 숫자 형식의 컬럼에 예상치 못한 값이 있는지, 또는 컬럼명이 정확한지 확인해보세요.")
    except Exception as e:
        st.error(f"파일 처리 또는 조 배정 중 예기치 않은 오류 발생: {e}")
        st.error("업로드한 Excel 파일의 내용과 형식을 다시 한번 확인해주세요. 문제가 지속되면 개발자에게 문의하세요.")
else:
    st.info("시작하려면 위에서 Excel 파일을 업로드해주세요.")

st.markdown("---")
st.markdown("Made with ❤️ by an AI Collaborator for You")
