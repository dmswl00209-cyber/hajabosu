"""담당자 화면 (내 PC). 접수 원문이 하자대장이 되기까지의 과정을 단계별로 보여준다.
실행: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import ai
import db
import rules
import run

BASE = Path(__file__).parent
접수함 = BASE / "data" / "접수함"

st.set_page_config(page_title="하자보수 도구", layout="wide")
st.title("하자보수 도구")
st.caption("접수 원문 → AI가 읽기 → 코드가 계산·판정 → 하자대장. 건마다 어떤 단계가 무엇을 했는지 보여줍니다.")


def 대장_읽기() -> pd.DataFrame | None:
    행들 = db.대장_읽기()
    return pd.DataFrame(행들, columns=db.대장_칸) if 행들 else None


tab과정, tab대장, tab구분 = st.tabs(["처리 과정", "하자대장", "AI·코드·사람 구분"])

# ───────────────────────── 처리 과정 ─────────────────────────
with tab과정:
    파일들 = sorted(p.name for p in 접수함.glob("*.txt"))
    선택 = st.selectbox("접수 원문", 파일들)
    원문 = (접수함 / 선택).read_text(encoding="utf-8")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("① 접수 원문")
        st.caption("현장 메모·메일·메신저. 형식이 제각각입니다.")
        st.code(원문, language=None)
    with c2:
        st.subheader("② AI가 읽은 값")
        st.caption("지침/접수정리.md대로 JSON 하나로만 답합니다. 호출할 때마다 API 비용이 듭니다.")
        키 = f"ai결과::{선택}"
        if st.button("AI로 읽기", type="primary"):
            with st.spinner("Claude가 읽는 중..."):
                try:
                    st.session_state[키] = ai.접수정리(원문)
                except Exception as e:
                    st.session_state[키] = None
                    st.error(f"{type(e).__name__}: {e}")
        결과 = st.session_state.get(키)
        if 결과:
            st.json(결과)
        else:
            st.info("‘AI로 읽기’를 누르면 결과가 여기에 나옵니다.")

    if 결과:
        st.divider()
        st.subheader("③ 코드가 계산·판정 (rules.py)")
        st.caption("AI를 쓰지 않습니다. 같은 입력이면 항상 같은 결과입니다.")
        접수일 = 결과.get("접수일") or run.파일명_날짜(선택)
        긴급 = rules.긴급도(결과["긴급근거"])
        기한 = rules.조치기한(접수일, 긴급)
        공사 = rules.공사정보_읽기()
        판정 = rules.보증판정(접수일, 결과["위치"], 결과["공종"], 공사)

        a, b, c = st.columns(3)
        a.metric("긴급도", 긴급)
        a.caption("누수·전기이상·안전위험 → 긴급 / 출입영업지장·고객민원 → 높음 / 그 외 보통")
        b.metric("조치기한", 기한.isoformat())
        b.caption(f"접수일 {접수일} + {rules.조치기한_일수[긴급]}일")
        c.metric("보증판정", 판정["보증판정"])
        c.caption(f"책임구분: {판정['책임구분'] or '—'}")

        후보 = [x for x in 공사 if x["위치"] == 결과["위치"]]
        st.markdown(f"**공사정보 조회** — 위치 `{결과['위치']}` · 공종 `{결과['공종']}`")
        if 후보:
            st.dataframe(pd.DataFrame(후보), hide_index=True, width="stretch")
        else:
            st.warning("위치가 같은 공사가 없습니다.")
        if 판정["보증판정"] == "확인필요":
            st.warning("확인필요: 위치·공종이 같은 공사를 하나로 정할 수 없습니다. 담당자가 현장을 보고 정합니다."
                       + (f"\n\n비고: {판정['비고']}" if 판정["비고"] else ""))
        else:
            st.success(f"{판정['공사번호']} {판정['시공업체']} · 준공 {판정['준공일']} → 보증만료 {판정['보증만료일']} "
                       f"· 접수일 {접수일} 기준 **{판정['보증판정']}**"
                       + (f" · 비고: {판정['비고']}" if 판정["비고"] else ""))

        st.divider()
        st.subheader("④ 사람이 할 일")
        if 판정["보증판정"] == "확인필요":
            st.write("현장을 보고 공종·공사를 정한 뒤 판정을 확정합니다.")
        else:
            st.write("AI가 읽은 값(특히 공종·긴급도)을 검수하고, 문제없으면 조치요청으로 넘깁니다.")
        st.caption("조치요청 전환·공문 작성은 아직 만들지 않았습니다. (6단계 이후)")

# ───────────────────────── 하자대장 ─────────────────────────
with tab대장:
    st.caption("접수함 전체를 처리해 DB 하자대장에 저장합니다. 접수번호가 같으면 덮어씁니다.")
    if st.button("접수함 전체 다시 처리"):
        with st.spinner("7건 처리 중..."):
            코드 = run.main()
        (st.success if 코드 == 0 else st.error)("처리 완료" if 코드 == 0 else "일부 건이 실패했습니다.")
    df = 대장_읽기()
    if df is None:
        st.info("하자대장에 아직 건이 없습니다. 위 버튼으로 만드세요.")
    else:
        확인 = (df["상태"] == "확인필요").sum()
        긴급수 = (df["긴급도"] == "긴급").sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("접수", f"{len(df)}건")
        m2.metric("긴급", f"{긴급수}건")
        m3.metric("확인필요", f"{확인}건")
        st.dataframe(
            df.style.apply(lambda r: ["background-color: #fff3cd" if r["상태"] == "확인필요" else "" for _ in r], axis=1),
            hide_index=True, width="stretch",
        )

# ───────────────────────── 구분 ─────────────────────────
with tab구분:
    st.table(pd.DataFrame([
        ["접수일·위치·공종·하자내용", "AI", "원문을 읽고 판단 (지침/접수정리.md)"],
        ["긴급 근거(누수·전기·안전·출입·민원)", "AI", "사실 여부만 true/false로 뽑음"],
        ["접수번호·긴급도·조치기한", "코드", "정해진 규칙 (rules.py)"],
        ["공사 조회·보증만료일·보증판정·책임구분", "코드", "접수일 기준 (rules.py)"],
        ["확인필요 건 확정", "사람", "현장 확인 후 결정"],
        ["AI 결과 검수·조치요청 전환", "사람", "외부로 나가는 일은 사람이 결정"],
    ], columns=["하는 일", "담당", "비고"]))
