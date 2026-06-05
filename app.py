import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ---------------- [안전하게 수정] 시스템 환경별 폰트 이름 지정 ----------------
if os.name == 'nt':  # 내 컴퓨터 (Windows 환경)
    font_name = "Malgun Gothic"
else:                # 스트림릿 클라우드 서버 (Linux 환경)
    font_name = "NanumGothic"  # packages.txt에 적은 나눔폰트가 자동으로 잡힙니다.

plt.rcParams['font.family'] = font_name
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style="whitegrid", font=font_name)
# -------------------------------------------------------------------------

# 대시보드 페이지 설정 (와이드 모드)
st.set_page_config(page_title="서울시 자치구 안전지수 대시보드", layout="wide")

@st.cache_data
def load_and_process_data():
    try:
        # 1. 범죄 데이터 로드 및 전처리
        crime_df = pd.read_csv("경찰청_범죄 발생 지역별 통계_20241231.csv", encoding='euc-kr')
        seoul_cols = [col for col in crime_df.columns if col.startswith("서울 ")]
        crime_sum = crime_df[seoul_cols].sum().reset_index()
        crime_sum.columns = ['자치구', '범죄건수']
        crime_sum['자치구'] = crime_sum['자치구'].str.replace("서울 ", "").str.strip()
        
        # 2. CCTV 데이터 로드 및 전처리
        cctv_df = pd.read_excel("서울시 자치구 (연도별) CCTV 설치현황_241231.xlsx", header=2)
        cctv_df.columns = cctv_df.columns.str.strip()
        
        col_gubun = [c for c in cctv_df.columns if '구분' in c][0]
        col_total = [c for c in cctv_df.columns if '총 계' in c or '총계' in c][0]
        
        cctv_filtered = cctv_df[[col_gubun, col_total]].dropna().copy()
        cctv_filtered.columns = ['자치구', 'CCTV수']
        cctv_filtered = cctv_filtered[~cctv_filtered['자치구'].str.contains('계|합계', na=False)]
        cctv_filtered['자치구'] = cctv_filtered['자치구'].str.replace(" ", "").str.strip()
        
        # 3. 데이터 병합 및 숫자 형변환
        merged_df = pd.merge(crime_sum, cctv_filtered, on='자치구', how='inner')
        if merged_df.empty: 
            return None
        
        merged_df['범죄건수'] = pd.to_numeric(merged_df['범죄건수'])
        merged_df['CCTV수'] = pd.to_numeric(merged_df['CCTV수'])
        
        # 4. 안전지수 공식 계산 (직관적인 상대평가 방식)
        max_cctv = merged_df['CCTV수'].max()         
        min_crime = merged_df['범죄건수'].min()        
        
        # CCTV 점수 계산 (CCTV 1등 구는 50점 만점)
        merged_df['CCTV 점수'] = (merged_df['CCTV수'] / max_cctv) * 50
        
        # 범죄 점수 계산 (범죄 최소 1등 구는 50점 만점)
        merged_df['범죄 점수'] = (min_crime / merged_df['범죄건수']) * 50
        
        # 최종 안전지수 합산 (100점 만점)
        merged_df['안전지수'] = merged_df['CCTV 점수'] + merged_df['범죄 점수']
        
        return merged_df.round(2)
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return None

raw_df = load_and_process_data()

if raw_df is not None:
    # ---------------- 사이드바 필터 설정 영역 ----------------
    st.sidebar.header("🔍 데이터 검색 및 필터")
    st.sidebar.markdown("원하는 조건으로 자치구를 필터링해보세요.")
    
    all_districts = sorted(raw_df['자치구'].unique())
    selected_districts = st.sidebar.multiselect(
        "확인할 자치구 선택",
        options=all_districts,
        default=all_districts
    )
    
    min_score = float(raw_df['안전지수'].min())
    max_score = float(raw_df