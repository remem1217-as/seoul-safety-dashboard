import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 한글 폰트 및 마이너스 깨짐 설정 (Windows 환경 최적화)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style="whitegrid", font='Malgun Gothic')

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
    max_score = float(raw_df['안전지수'].max())
    score_range = st.sidebar.slider(
        "최소~최대 안전지수 설정",
        min_value=min_score,
        max_value=max_score,
        value=(min_score, max_score),
        step=0.1
    )
    
    st.sidebar.write("---")
    st.sidebar.info("💡 사이드바의 필터를 변경하면 우측의 모든 데이터와 그래프가 실시간으로 바뀝니다.")
    
    # 필터 데이터 반영
    df = raw_df[
        (raw_df['자치구'].isin(selected_districts)) & 
        (raw_df['안전지수'] >= score_range[0]) & 
        (raw_df['안전지수'] <= score_range[1])
    ]
    
    # ---------------- 본문 UI 구성 ----------------
    st.title("🛡️ 서울시 자치구별 안전지수 대시보드")
    st.caption("경찰청 범죄 통계와 자치구별 CCTV 현황 데이터를 융합한 분석 대시보드입니다.")
    st.write("---")
    
    if df.empty:
        st.warning("⚠️ 필터 조건에 맞는 자치구가 없습니다. 사이드바 설정을 다시 변경해 주세요.")
    else:
        # KPI 카드
        df_sorted = df.sort_values(by='안전지수', ascending=False)
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("분석 대상 자치구 수", f"{len(df)}개")
        kpi2.metric("선택 자치구 평균 안전지수", f"{df['안전지수'].mean():.2f} 점")
        kpi3.metric("필터 내 최고 안전 구", f"{df_sorted.iloc[0]['자치구']} ({df_sorted.iloc[0]['안전지수']}점)")
        st.write("---")
        
        # 메인 콘텐츠 영역 (좌: 막대그래프 / 우: 테이블)
        left, right = st.columns([6, 4])
        with left:
            st.subheader("📊 자치구별 안전지수 순위")
            
            fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.3)))
            bars = sns.barplot(x='안전지수', y='자치구', data=df_sorted, palette='coolwarm', ax=ax)
            
            ax.set_title('서울시 자치구별 안전지수 (점수가 높을수록 안전)', fontsize=13, weight='bold', pad=20)
            ax.set_xlabel('안전지수 (100점 만점)', fontsize=11, labelpad=10)
            ax.set_ylabel('자치구', fontsize=11, labelpad=10)
            ax.tick_params(axis='y', labelsize=10)
            
            for bar in bars.patches:
                width = bar.get_width()
                if width > 0:
                    ax.text(width + 1, bar.get_y() + bar.get_height()/2, f'{width:.1f}', 
                            va='center', ha='left', fontsize=9, color='black', weight='bold')
                
            plt.subplots_adjust(left=0.22, right=0.90, top=0.90, bottom=0.12)
            st.pyplot(fig)
            
        with right:
            st.subheader("🏆 안전지수 상세 순위")
            st.dataframe(df_sorted[['자치구', '안전지수', 'CCTV 점수', '범죄 점수']].reset_index(drop=True), use_container_width=True, height=455)
        st.write("---")
        
        # 하단 섹션: 비교 시각화
        st.subheader("🔄 원본 지표 비교 (CCTV 수 vs 범죄 건수)")
        df_compare = df.sort_values(by='자치구')
        x = range(len(df_compare))
        
        fig2, ax2 = plt.subplots(figsize=(12, 5.5))
        
        bar1 = ax2.bar([i - 0.2 for i in x], df_compare['CCTV수'], width=0.4, label='CCTV 설치수(대)', color='#5bc0de')
        ax2.set_ylabel('CCTV 설치수 (대)', color='#5bc0de', weight='bold', labelpad=10)
        ax2.tick_params(axis='y', labelcolor='#5bc0de')
        
        ax2_twin = ax2.twinx()
        bar2 = ax2_twin.bar([i + 0.2 for i in x], df_compare['범죄건수'], width=0.4, label='범죄 발생건수(건)', color='#d9534f')
        ax2_twin.set_ylabel('범죄 발생건수 (건)', color='#d9534f', weight='bold', labelpad=10)
        ax2_twin.tick_params(axis='y', labelcolor='#d9534f')
        
        ax2.set_xticks(x)
        ax2.set_xticklabels(df_compare['자치구'], rotation=45, ha='right', fontsize=10)
        ax2.set_title('자치구별 CCTV 보유량과 범죄 건수 동시 비교', fontsize=13, weight='bold', pad=15)
        
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left', bbox_to_anchor=(1.08, 1))
        
        plt.tight_layout()
        st.pyplot(fig2)
        
        with st.expander("🔍 선택한 자치구 전체 원본 데이터 테이블 보기"):
            st.dataframe(df_sorted.reset_index(drop=True), use_container_width=True)