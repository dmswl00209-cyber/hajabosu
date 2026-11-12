"""접수 화면 (웹에 배포, 매장·현장용). 하자 접수를 받아 DB 접수 테이블에 저장만 한다.
AI·판정은 하지 않는다 (담당자 PC의 run.py가 처리). 다른 사람의 접수 내용은 보여주지 않는다.
실행: streamlit run intake.py"""
from datetime import date

import streamlit as st

import db

st.set_page_config(page_title="하자 접수", layout="centered")
st.title("하자 접수")
st.caption("건물에서 발견한 하자나 불편을 알려 주세요. 시설관리팀이 확인합니다.")

with st.form("접수", clear_on_submit=True):
    발견일 = st.date_input("발견일", value=date.today(), max_value=date.today())
    접수자 = st.text_input("접수자", placeholder="이름")
    부서 = st.text_input("부서 / 매장", placeholder="예: 5F 레스토랑가 운영파트, 4F 입점매장")
    위치 = st.text_input("위치", placeholder="예: B1 푸드코트, 2F 여자화장실 세면대 앞")
    내용 = st.text_area("내용", placeholder="어떤 문제인지, 언제부터인지, 임시 조치를 했다면 함께 적어 주세요.", height=160)
    보내기 = st.form_submit_button("접수하기", type="primary")

if 보내기:
    값 = {"접수자": 접수자.strip(), "부서": 부서.strip(), "위치": 위치.strip(), "내용": 내용.strip()}
    비었음 = [이름 for 이름, v in 값.items() if not v]
    if 비었음:
        st.error("다음 항목을 적어 주세요: " + ", ".join(비었음))
    else:
        try:
            번호 = db.접수_저장(발견일, **값)
            st.success(f"접수되었습니다. (접수 {번호}번)")
        except Exception:
            st.error("저장하지 못했습니다. 잠시 뒤 다시 시도하거나 시설관리팀에 알려 주세요.")
