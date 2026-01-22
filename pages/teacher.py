# teacher.py
# ==================================================
# 교사용 대시보드 - 학생 서술형 평가 결과 조회 및 분석
# ==================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# ── Supabase 클라이언트 초기화 ──
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

# ── 데이터 조회 함수 ──
@st.cache_data(ttl=60)  # 60초 캐시 (새로고침 시 최신 데이터 반영)
def load_submissions(start_date=None, end_date=None):
    """Supabase에서 제출 데이터를 가져옵니다."""
    supabase = get_supabase_client()
    
    query = supabase.table("student_submissions").select("*")
    
    # 날짜 필터링
    if start_date:
        query = query.gte("created_at", start_date.isoformat())
    if end_date:
        # 해당 날짜의 23:59:59까지 포함
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.lte("created_at", end_datetime.isoformat())
    
    # 최신순 정렬
    query = query.order("created_at", desc=True)
    
    response = query.execute()
    return response.data

# ── O/X 판정 추출 함수 ──
def extract_result(feedback: str) -> str:
    """피드백에서 O/X 판정만 추출"""
    if not feedback:
        return "?"
    if feedback.startswith("O:"):
        return "O"
    elif feedback.startswith("X:"):
        return "X"
    return "?"

# ── 메인 대시보드 ──
st.set_page_config(page_title="교사 대시보드", page_icon="📊", layout="wide")

st.title("📊 학생 서술형 평가 - 교사 대시보드")
st.markdown("---")

# ── 사이드바: 필터 옵션 ──
with st.sidebar:
    st.header("🔍 필터 옵션")
    
    # 날짜 범위 선택
    date_filter = st.checkbox("날짜 필터 사용", value=False)
    
    if date_filter:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "시작 날짜",
                value=datetime.now().date() - timedelta(days=7)
            )
        with col2:
            end_date = st.date_input(
                "종료 날짜",
                value=datetime.now().date()
            )
    else:
        start_date = None
        end_date = None
    
    # 새로고침 버튼
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 데이터 로드 ──
try:
    data = load_submissions(start_date, end_date)
    
    if not data:
        st.warning("제출된 데이터가 없습니다.")
        st.stop()
    
    df = pd.DataFrame(data)
    
    # created_at을 datetime으로 변환
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["제출일시"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
    
    # O/X 결과 추출
    df["결과1"] = df["feedback_1"].apply(extract_result)
    df["결과2"] = df["feedback_2"].apply(extract_result)
    df["결과3"] = df["feedback_3"].apply(extract_result)
    
except Exception as e:
    st.error(f"데이터 로드 오류: {e}")
    st.stop()

# ── 1. 전체 통계 개요 ──
st.header("📈 전체 통계")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("총 제출 수", len(df))

with col2:
    unique_students = df["student_id"].nunique()
    st.metric("제출 학생 수", unique_students)

with col3:
    latest_submission = df["created_at"].max().strftime("%m/%d %H:%M")
    st.metric("최근 제출", latest_submission)

with col4:
    # 평균 정답 개수
    total_correct = (
        (df["결과1"] == "O").sum() +
        (df["결과2"] == "O").sum() +
        (df["결과3"] == "O").sum()
    )
    avg_correct = total_correct / len(df) if len(df) > 0 else 0
    st.metric("평균 정답 수", f"{avg_correct:.1f} / 3")

st.markdown("---")

# ── 2. 문항별 정답률 ──
st.header("📝 문항별 정답률")

q_cols = st.columns(3)

for i, col in enumerate(q_cols, start=1):
    with col:
        result_col = f"결과{i}"
        total = len(df)
        correct = (df[result_col] == "O").sum()
        incorrect = (df[result_col] == "X").sum()
        unknown = (df[result_col] == "?").sum()
        
        correct_rate = (correct / total * 100) if total > 0 else 0
        
        st.subheader(f"문항 {i}")
        st.metric("정답률", f"{correct_rate:.1f}%")
        
        # 간단한 막대 차트
        chart_data = pd.DataFrame({
            "판정": ["O", "X", "?"],
            "학생 수": [correct, incorrect, unknown]
        })
        st.bar_chart(chart_data.set_index("판정"))

st.markdown("---")

# ── 3. 학생별 제출 내역 (테이블) ──
st.header("📋 학생별 제출 내역")

# 학번 검색
search_id = st.text_input("🔎 학번으로 검색", placeholder="예: 10130")

# 검색 필터링
display_df = df.copy()
if search_id.strip():
    display_df = display_df[display_df["student_id"].str.contains(search_id.strip())]

# 표시할 컬럼 선택
display_columns = ["student_id", "제출일시", "결과1", "결과2", "결과3"]
st.dataframe(
    display_df[display_columns],
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ── 4. 상세 조회 (학생별) ──
st.header("🔍 상세 답안 조회")

# 학생 선택
student_ids = sorted(df["student_id"].unique())
selected_student = st.selectbox("학생 선택", student_ids)

if selected_student:
    student_data = df[df["student_id"] == selected_student].sort_values("created_at", ascending=False)
    
    if len(student_data) > 1:
        st.info(f"💡 {selected_student} 학생은 총 {len(student_data)}번 제출했습니다.")
        submission_index = st.radio(
            "제출 선택",
            range(len(student_data)),
            format_func=lambda x: f"{x+1}번째 제출 ({student_data.iloc[x]['제출일시']})",
            horizontal=True
        )
    else:
        submission_index = 0
    
    selected_row = student_data.iloc[submission_index]
    
    # 3개 문항 표시
    for i in range(1, 4):
        st.markdown(f"### 문항 {i}")
        
        col_a, col_b = st.columns([1, 1])
        
        with col_a:
            st.markdown("**📝 학생 답안**")
            answer = selected_row[f"answer_{i}"]
            st.text_area(
                f"답안 {i}",
                value=answer,
                height=100,
                disabled=True,
                label_visibility="collapsed"
            )
        
        with col_b:
            st.markdown("**🤖 AI 피드백**")
            feedback = selected_row[f"feedback_{i}"]
            
            # O/X에 따라 색상 구분
            if feedback.startswith("O:"):
                st.success(feedback)
            elif feedback.startswith("X:"):
                st.error(feedback)
            else:
                st.info(feedback)
        
        # 채점 기준 표시
        with st.expander(f"📌 문항 {i} 채점 기준"):
            guideline = selected_row[f"guideline_{i}"]
            st.write(guideline)
        
        st.markdown("---")
    
    # 메타 정보
    with st.expander("ℹ️ 제출 정보"):
        st.write(f"**모델**: {selected_row['model']}")
        st.write(f"**제출 시각**: {selected_row['제출일시']}")

st.markdown("---")

# ── 5. 데이터 다운로드 ──
st.header("💾 데이터 다운로드")

col1, col2 = st.columns(2)

with col1:
    # CSV 다운로드
    csv = df.to_csv(index=False).encode('utf-8-sig')  # 한글 깨짐 방지
    st.download_button(
        label="📥 전체 데이터 CSV 다운로드",
        data=csv,
        file_name=f"학생평가결과_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )

with col2:
    # 요약 통계 다운로드
    summary_df = pd.DataFrame({
        "학번": df["student_id"],
        "제출일시": df["제출일시"],
        "문항1": df["결과1"],
        "문항2": df["결과2"],
        "문항3": df["결과3"],
        "정답개수": (df["결과1"] == "O").astype(int) + 
                   (df["결과2"] == "O").astype(int) + 
                   (df["결과3"] == "O").astype(int)
    })
    
    summary_csv = summary_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 요약 통계 CSV 다운로드",
        data=summary_csv,
        file_name=f"요약통계_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ── Footer ──
st.markdown("---")
st.caption("📊 학생 서술형 평가 교사 대시보드 v1.0")
