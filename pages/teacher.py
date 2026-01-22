# teacher.py
# ==================================================
# 교사용 대시보드 - 학생 서술형 평가 결과 조회 및 분석
# (비밀번호 인증 + 상세 성적표 다운로드 기능 추가)
# ==================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
import io

# ── Supabase 클라이언트 초기화 ──
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

# ── 비밀번호 확인 함수 ──
def check_password():
    """비밀번호 확인 후 대시보드 접근 허용"""
    
    # 세션 상태 초기화
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    # 이미 인증된 경우 True 반환
    if st.session_state.password_correct:
        return True
    
    # 로그인 화면
    st.title("🔐 교사 대시보드 로그인")
    st.markdown("---")
    
    # 비밀번호 입력
    password = st.text_input("비밀번호를 입력하세요", type="password", key="password_input")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("로그인", use_container_width=True):
            # secrets.toml에서 비밀번호 확인
            try:
                correct_password = st.secrets["TEACHER_PASSWORD"]
                
                if password == correct_password:
                    st.session_state.password_correct = True
                    st.success("✅ 로그인 성공!")
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 틀렸습니다.")
            except KeyError:
                st.error("⚠️ secrets.toml에 TEACHER_PASSWORD가 설정되지 않았습니다.")
    
    with col2:
        if st.button("취소", use_container_width=True):
            st.stop()
    
    # 비밀번호 설정 안내
    with st.expander("ℹ️ 비밀번호 설정 방법"):
        st.markdown("""
        `.streamlit/secrets.toml` 파일에 다음 줄을 추가하세요:
```toml
        TEACHER_PASSWORD = "원하는비밀번호"
```
        
        예시:
```toml
        TEACHER_PASSWORD = "teacher2024"
```
        """)
    
    return False

# ── 데이터 조회 함수 ──
@st.cache_data(ttl=60)
def load_submissions(start_date=None, end_date=None):
    """Supabase에서 제출 데이터를 가져옵니다."""
    supabase = get_supabase_client()
    
    query = supabase.table("student_submissions").select("*")
    
    if start_date:
        query = query.gte("created_at", start_date.isoformat())
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.lte("created_at", end_datetime.isoformat())
    
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

# ── 점수 계산 함수 ──
def calculate_score(result: str) -> int:
    """O/X 결과를 점수로 변환 (O=1, X=0, ?=0)"""
    return 1 if result == "O" else 0

# ── 상세 성적표 생성 함수 ──
def create_detailed_grade_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """학생별 상세 성적표 생성"""
    
    grade_data = []
    
    for _, row in df.iterrows():
        record = {
            "학번": row["student_id"],
            "제출일시": row["제출일시"],
            
            # 문항 1
            "문항1_결과": row["결과1"],
            "문항1_점수": calculate_score(row["결과1"]),
            "문항1_답안": row["answer_1"],
            "문항1_피드백": row["feedback_1"],
            
            # 문항 2
            "문항2_결과": row["결과2"],
            "문항2_점수": calculate_score(row["결과2"]),
            "문항2_답안": row["answer_2"],
            "문항2_피드백": row["feedback_2"],
            
            # 문항 3
            "문항3_결과": row["결과3"],
            "문항3_점수": calculate_score(row["결과3"]),
            "문항3_답안": row["answer_3"],
            "문항3_피드백": row["feedback_3"],
            
            # 총점
            "총점": (calculate_score(row["결과1"]) + 
                    calculate_score(row["결과2"]) + 
                    calculate_score(row["결과3"])),
        }
        grade_data.append(record)
    
    return pd.DataFrame(grade_data)

# ── 성적 요약표 생성 함수 ──
def create_summary_grade_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """학생별 최종 성적 요약표 (최신 제출 기준)"""
    
    # 각 학생의 최신 제출만 추출
    latest_df = df.sort_values("created_at", ascending=False).groupby("student_id").first().reset_index()
    
    summary_data = []
    
    for _, row in latest_df.iterrows():
        record = {
            "학번": row["student_id"],
            "제출일시": row["제출일시"],
            "문항1": row["결과1"],
            "문항2": row["결과2"],
            "문항3": row["결과3"],
            "정답개수": (calculate_score(row["결과1"]) + 
                       calculate_score(row["결과2"]) + 
                       calculate_score(row["결과3"])),
            "총점": (calculate_score(row["결과1"]) + 
                    calculate_score(row["결과2"]) + 
                    calculate_score(row["결과3"])),
        }
        summary_data.append(record)
    
    return pd.DataFrame(summary_data).sort_values("학번")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 애플리케이션
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(page_title="교사 대시보드", page_icon="📊", layout="wide")

# ── 비밀번호 확인 (통과하지 못하면 여기서 중단) ──
if not check_password():
    st.stop()

# ── 상단 헤더 (로그아웃 버튼 포함) ──
col1, col2 = st.columns([4, 1])
with col1:
    st.title("📊 학생 서술형 평가 - 교사 대시보드")
with col2:
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.password_correct = False
        st.rerun()

st.markdown("---")

# ── 사이드바: 필터 옵션 ──
with st.sidebar:
    st.header("🔍 필터 옵션")
    
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
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["제출일시"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
    
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
        
        chart_data = pd.DataFrame({
            "판정": ["O", "X", "?"],
            "학생 수": [correct, incorrect, unknown]
        })
        st.bar_chart(chart_data.set_index("판정"))

st.markdown("---")

# ── 3. 학생별 제출 내역 (테이블) ──
st.header("📋 학생별 제출 내역")

search_id = st.text_input("🔎 학번으로 검색", placeholder="예: 10130")

display_df = df.copy()
if search_id.strip():
    display_df = display_df[display_df["student_id"].str.contains(search_id.strip())]

display_columns = ["student_id", "제출일시", "결과1", "결과2", "결과3"]
st.dataframe(
    display_df[display_columns],
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ── 4. 상세 조회 (학생별) ──
st.header("🔍 상세 답안 조회")

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
            
            if feedback.startswith("O:"):
                st.success(feedback)
            elif feedback.startswith("X:"):
                st.error(feedback)
            else:
                st.info(feedback)
        
        with st.expander(f"📌 문항 {i} 채점 기준"):
            guideline = selected_row[f"guideline_{i}"]
            st.write(guideline)
        
        st.markdown("---")
    
    with st.expander("ℹ️ 제출 정보"):
        st.write(f"**모델**: {selected_row['model']}")
        st.write(f"**제출 시각**: {selected_row['제출일시']}")

st.markdown("---")

# ── 5. 성적표 다운로드 (강화된 기능) ──
st.header("💾 성적표 다운로드")

st.markdown("### 📊 다운로드 옵션")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 1️⃣ 상세 성적표 (전체)")
    st.caption("모든 제출 내역 + 답안 + 피드백 포함")
    
    detailed_df = create_detailed_grade_sheet(df)
    
    # CSV 변환
    csv_detailed = detailed_df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 상세 성적표 다운로드 (CSV)",
        data=csv_detailed,
        file_name=f"상세성적표_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # 미리보기
    with st.expander("👀 상세 성적표 미리보기 (처음 5명)"):
        st.dataframe(detailed_df.head(), use_container_width=True)

with col2:
    st.markdown("#### 2️⃣ 최종 성적 요약표")
    st.caption("학생별 최신 제출 기준 요약")
    
    summary_df = create_summary_grade_sheet(df)
    
    # CSV 변환
    csv_summary = summary_df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 최종 성적표 다운로드 (CSV)",
        data=csv_summary,
        file_name=f"최종성적표_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # 미리보기
    with st.expander("👀 최종 성적표 미리보기"):
        st.dataframe(summary_df, use_container_width=True)

st.markdown("---")

# ── 6. 추가 다운로드 옵션 ──
with st.expander("📋 기타 다운로드 옵션"):
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**전체 데이터 (Raw)**")
        csv_raw = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 전체 데이터 다운로드",
            data=csv_raw,
            file_name=f"전체데이터_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col_b:
        st.markdown("**문항별 통계**")
        
        stats_data = {
            "문항": ["문항 1", "문항 2", "문항 3"],
            "정답(O)": [
                (df["결과1"] == "O").sum(),
                (df["결과2"] == "O").sum(),
                (df["결과3"] == "O").sum()
            ],
            "오답(X)": [
                (df["결과1"] == "X").sum(),
                (df["결과2"] == "X").sum(),
                (df["결과3"] == "X").sum()
            ],
            "정답률(%)": [
                round((df["결과1"] == "O").sum() / len(df) * 100, 1),
                round((df["결과2"] == "O").sum() / len(df) * 100, 1),
                round((df["결과3"] == "O").sum() / len(df) * 100, 1)
            ]
        }
        
        stats_df = pd.DataFrame(stats_data)
        csv_stats = stats_df.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="📥 문항별 통계 다운로드",
            data=csv_stats,
            file_name=f"문항통계_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ── Footer ──
st.markdown("---")
st.caption("📊 학생 서술형 평가 교사 대시보드 v2.0 (비밀번호 인증 + 상세 성적표)")
