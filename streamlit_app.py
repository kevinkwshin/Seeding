import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Helper function to assign teams
def assign_teams(df, cutoff_date_dt, num_target_teams):
    df_processed = df.copy()
    
    # '들어온 날짜'가 문자열일 경우 datetime으로 변환 시도
    if not pd.api.types.is_datetime64_any_dtype(df_processed['들어온 날짜']):
        try:
            df_processed['들어온 날짜'] = pd.to_datetime(df_processed['들어온 날짜'], errors='coerce')
        except Exception as e:
            st.error(f"'들어온 날짜' 컬럼을 날짜 형식으로 변환 중 오류 발생: {e}")
            st.info("Excel에서 '들어온 날짜' 컬럼 형식을 'YYYY-MM-DD' 등으로 확인해주세요.")
            return None

    if df_processed['들어온 날짜'].isnull().any():
        st.warning("'들어온 날짜'에 누락된 값이 있습니다. 해당 행은 신규/기존 분류에서 제외될 수 있습니다.")
        # 누락된 값을 아주 오래된 날짜로 처리하여 기존 멤버로 간주하거나, 사용자가 결정하도록 할 수 있음
        # 여기서는 일단 그대로 진행 (NaT < cutoff_date_dt 는 False가 됨)

    # 1. 기존 멤버와 신규 멤버 분리
    existing_members_df = df_processed[df_processed['들어온 날짜'] <= cutoff_date_dt].sample(frac=1, random_state=42).reset_index(drop=True)
    new_members_df = df_processed[df_processed['들어온 날짜'] > cutoff_date_dt].sample(frac=1, random_state=24).reset_index(drop=True)

    st.write(f"총 인원: {len(df_processed)}, 기존 인원: {len(existing_members_df)}, 신규 인원: {len(new_members_df)}")

    if num_target_teams <= 0:
        st.error("조 개수는 1 이상이어야 합니다.")
        return None

    # 각 멤버의 원본 인덱스를 저장해두었다가 나중에 매핑
    # DataFrame에 직접 '새로운 조' 컬럼을 추가하기 위해 원본 인덱스 사용
    member_to_new_team = {} # {original_df_index: team_name}

    # 2. 기존 멤버 배정 (Round-robin)
    teams_composition = {f"새로운 조 {i+1}": [] for i in range(num_target_teams)} # {team_name: [original_df_index, ...]}
    
    for i, row in existing_members_df.iterrows():
        original_idx = df.index[df['이름'] == row['이름']].tolist()[0] # 이름으로 원본 인덱스 찾기 (이름이 유니크하다고 가정)
                                                                   # 더 안전하게는 업로드 시 df에 고유 ID 부여
        team_idx = i % num_target_teams
        team_name = f"새로운 조 {team_idx + 1}"
        teams_composition[team_name].append(original_idx)
        member_to_new_team[original_idx] = team_name

    # 3. 신규 멤버 배정 (가장 작은 팀에 우선 배정)
    for i, row in new_members_df.iterrows():
        original_idx = df.index[df['이름'] == row['이름']].tolist()[0]

        # 현재 팀별 인원수 계산
        team_sizes = {name: len(members) for name, members in teams_composition.items()}
        
        # 가장 인원수가 적은 팀 찾기 (동점 시 이름순으로 첫 번째)
        # 주의: team_sizes가 비어있을 수 없음 (num_target_teams > 0 이므로)
        smallest_team_name = min(team_sizes, key=lambda k: (team_sizes[k], k))
        
        teams_composition[smallest_team_name].append(original_idx)
        member_to_new_team[original_idx] = smallest_team_name
        
    # 4. 결과 DataFrame 생성
    df_result = df.copy()
    # df_result['새로운 조'] = pd.Series(dtype=str) # 컬럼 미리 생성
    # for original_idx, team_name in member_to_new_team.items():
    #     df_result.loc[original_idx, '새로운 조'] = team_name
    
    # 더 간단한 방법: map 사용
    df_result['새로운 조'] = df_result.index.map(member_to_new_team)


    return df_result

# Streamlit App UI
st.set_page_config(layout="wide")
st.title("🧑‍🤝‍🧑 AI 조 배정 도우미 🤖")

st.markdown("""
이 앱은 Excel 파일을 업로드 받아 여러 특성을 고려하여 새로운 조를 배정합니다.
- **파일 형식**: Excel (.xlsx, .xls)
- **필수 컬럼**: '이름', '들어온 날짜'
- **권장 컬럼**: '현재조', '거듭남', '성향', '나이', '참여율' 등 (더 많은 특성 컬럼이 있어도 괜찮습니다.)
- **신규 인원 기준**: 입력하신 날짜 이후에 '들어온 날짜'를 가진 사람은 신규 인원으로 분류됩니다.
- **조 배정 로직**:
    1. 기존 인원: 무작위로 섞어 지정된 조 개수에 최대한 균등하게 배정합니다.
    2. 신규 인원: 기존 인원으로 구성된 조 중 가장 인원이 적은 조에 우선 배정합니다.
""")

uploaded_file = st.file_uploader("조 편성할 명단 Excel 파일 업로드", type=["xlsx", "xls"])

if uploaded_file:
    try:
        df_input = pd.read_excel(uploaded_file)
        st.subheader("업로드된 데이터 일부:")
        st.dataframe(df_input.head())

        # 필수 컬럼 확인
        required_cols = ["이름", "들어온 날짜"]
        missing_cols = [col for col in required_cols if col not in df_input.columns]
        if missing_cols:
            st.error(f"필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")
        else:
            # 날짜 형식 확인 및 변환 시도 (assign_teams 함수 내에서도 처리하지만, 여기서 미리 사용자에게 알려줄 수 있음)
            try:
                # to_datetime으로 변환 시도. 실패하면 원본 유지하고 함수 내에서 다시 처리.
                pd.to_datetime(df_input['들어온 날짜'], errors='raise')
            except Exception:
                st.warning("'들어온 날짜' 컬럼이 표준 날짜 형식이 아닐 수 있습니다. 'YYYY-MM-DD' 또는 'MM/DD/YYYY' 형식 등을 권장합니다.")


            # 신규 인원 기준 날짜 입력
            # 기본값은 오늘 날짜보다 조금 이전으로 설정하거나, 데이터의 최대 날짜를 참고할 수 있음
            default_cutoff_date = datetime.now().date()
            if pd.api.types.is_datetime64_any_dtype(df_input['들어온 날짜']):
                 # 에러 없이 변환된 경우, 데이터 내 날짜를 참고하여 기본값 설정 가능
                valid_dates = pd.to_datetime(df_input['들어온 날짜'], errors='coerce').dropna()
                if not valid_dates.empty:
                    default_cutoff_date = valid_dates.quantile(0.8).date() # 예: 상위 80% 지점 날짜
            
            cutoff_date = st.date_input("신규 인원 기준 날짜 (이 날짜 이후 들어온 사람 = 신규)", 
                                        value=default_cutoff_date,
                                        help="이 날짜까지 포함하여 그 이전에 들어온 사람은 '기존 인원'으로 분류됩니다.")
            
            # 원하는 조 개수 입력
            # '현재조' 컬럼이 있다면, 그 조 개수를 기본값으로 제안
            default_num_teams = 3 # 기본값
            if '현재조' in df_input.columns:
                # NaN 값을 제외하고 유니크한 조의 개수 계산
                unique_current_teams = df_input['현재조'].dropna().nunique()
                if unique_current_teams > 0:
                    default_num_teams = unique_current_teams
            
            num_target_teams = st.number_input("배정할 새로운 조의 총 개수:", 
                                               min_value=1, 
                                               value=int(default_num_teams), # int로 변환
                                               step=1)

            if st.button("🚀 새로운 조 배정 시작!"):
                if cutoff_date:
                    cutoff_date_dt = pd.to_datetime(cutoff_date) # datetime.date to datetime64
                    
                    with st.spinner("조를 배정 중입니다... 잠시만 기다려주세요."):
                        df_result = assign_teams(df_input, cutoff_date_dt, num_target_teams)
                    
                    if df_result is not None:
                        st.subheader("🎉 새로운 조 배정 결과:")
                        st.dataframe(df_result)

                        st.subheader("📊 조별 요약:")
                        summary_list = []
                        if '새로운 조' in df_result.columns and not df_result['새로운 조'].isnull().all():
                            # NaN 값을 가진 '새로운 조'를 필터링 (배정 안된 경우)
                            grouped_results = df_result.dropna(subset=['새로운 조']).groupby('새로운 조')
                            
                            for team_name, group_df in grouped_results:
                                team_summary = {'조 이름': team_name, '인원수': len(group_df)}
                                
                                # 수치형 데이터 요약 (존재하는 경우)
                                if '나이' in group_df.columns and pd.api.types.is_numeric_dtype(group_df['나이']):
                                    team_summary['평균 나이'] = round(group_df['나이'].mean(), 1) if not group_df['나이'].isnull().all() else 'N/A'
                                if '참여율' in group_df.columns and pd.api.types.is_numeric_dtype(group_df['참여율']):
                                    team_summary['평균 참여율'] = round(group_df['참여율'].mean(), 2) if not group_df['참여율'].isnull().all() else 'N/A'
                                
                                # 범주형 데이터 요약 (존재하는 경우)
                                for cat_col in ['성향', '거듭남']: # 필요에 따라 추가
                                    if cat_col in group_df.columns:
                                        counts = group_df[cat_col].value_counts().to_dict()
                                        # 보기 좋게 문자열로 변환
                                        team_summary[f'{cat_col} 분포'] = ', '.join([f"{k}({v})" for k,v in counts.items()]) if counts else 'N/A'
                                
                                summary_list.append(team_summary)
                            
                            if summary_list:
                                summary_df = pd.DataFrame(summary_list)
                                st.dataframe(summary_df)
                            else:
                                st.info("요약할 데이터가 없습니다. 배정된 조가 있는지 확인해주세요.")

                            # 다운로드 버튼
                            @st.cache_data # Streamlit 1.2 caching
                            def convert_df_to_csv(df):
                                return df.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지

                            csv = convert_df_to_csv(df_result)
                            st.download_button(
                                label="결과 CSV 파일로 다운로드",
                                data=csv,
                                file_name=f"새로운_조_배정_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.warning("새로운 조가 배정되지 않았거나, '새로운 조' 컬럼이 결과에 없습니다.")
                else:
                    st.error("신규 인원 기준 날짜를 선택해주세요.")
    except Exception as e:
        st.error(f"파일 처리 중 오류 발생: {e}")
        st.error("Excel 파일 형식이 올바른지, 또는 파일이 손상되지 않았는지 확인해주세요.")
else:
    st.info("시작하려면 Excel 파일을 업로드해주세요.")

st.markdown("---")
st.markdown("Made with ❤️ by an AI Collaborator")
