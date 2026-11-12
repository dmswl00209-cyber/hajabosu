"""접수함 파일과 DB 접수(미처리)를 모두 처리해 하자대장(DB)에 저장한다.
흐름: 원문 -> ai.접수정리(AI가 읽는 칸) -> rules(번호·기한·판정) -> db.대장_저장
DB 접수는 발견일을 접수일로 쓰고, 저장이 끝나면 접수의 처리상태를 처리완료로 바꾼다."""
import re
import sys
from pathlib import Path

import ai
import db
import rules

BASE = Path(__file__).parent
접수함 = BASE / "data" / "접수함"


def 파일명_날짜(파일명: str) -> str | None:
    """'01_20261102_...' -> '2026-11-02'. 접수일이 원문에 없을 때만 쓴다."""
    m = re.match(r"^\d+_(\d{4})(\d{2})(\d{2})_", 파일명)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def 접수원문(접수: dict) -> str:
    """DB 접수 1건을 AI가 읽을 글로 만든다."""
    return (f"[접수 화면] 발견일 {접수['발견일']}\n"
            f"접수자: {접수['접수자']} ({접수['부서']})\n"
            f"위치: {접수['위치']}\n\n{접수['내용']}\n")


class 번호부여:
    """접수번호 순번. 같은 원문파일이면 기존 번호를 다시 쓰고(덮어쓰기), 새 건은 그날의 빈 순번을 쓴다."""

    def __init__(self):
        기존 = db.대장_읽기()
        self.원문별 = {r["원문파일"]: r["접수번호"] for r in 기존}
        self.사용 = {r["접수번호"] for r in 기존}

    def 새로(self, 접수일: str, 원문파일: str) -> str:
        if 원문파일 in self.원문별:
            return self.원문별[원문파일]
        순번 = 1
        while rules.접수번호(접수일, 순번) in self.사용:
            순번 += 1
        번호 = rules.접수번호(접수일, 순번)
        self.사용.add(번호)
        self.원문별[원문파일] = 번호
        return 번호


def 대장행(원문: str, 원문파일: str, 접수일_지정: str | None, 공사: list[dict], 번호: 번호부여) -> dict:
    결과 = ai.접수정리(원문)
    접수일 = 접수일_지정 or 결과.get("접수일") or 파일명_날짜(원문파일)
    if not 접수일:
        raise ValueError("접수일을 원문과 파일명 어디에서도 찾지 못했습니다.")
    긴급 = rules.긴급도(결과["긴급근거"])
    판정 = rules.보증판정(접수일, 결과["위치"], 결과["공종"], 공사)
    행 = {
        "접수번호": 번호.새로(접수일, 원문파일),
        "접수일": 접수일,
        "원문파일": 원문파일,
        "위치": 결과["위치"],
        "공종": 결과["공종"],
        "하자내용": 결과["하자내용"],
        "긴급도": 긴급,
        "조치기한": rules.조치기한(접수일, 긴급).isoformat(),
        **판정,
        "상태": "확인필요" if 판정["보증판정"] == "확인필요" else "판정완료",
    }
    if len(행["하자내용"]) > 40:
        print(f"  주의: {원문파일} 하자내용이 40자를 넘습니다({len(행['하자내용'])}자).")
    return 행


def main() -> int:
    공사 = rules.공사정보_읽기()
    번호 = 번호부여()
    행들, 실패 = [], []
    완료할_접수 = []  # (접수 id, 접수번호)

    # 1) 접수함 파일: 접수일은 원문에 적힌 날짜(없으면 파일명)
    for 파일 in sorted(접수함.glob("*.txt")):
        try:
            행 = 대장행(파일.read_text(encoding="utf-8"), 파일.name, None, 공사, 번호)
            행들.append(행)
            print(f"{행['접수번호']}  {파일.name}  {행['긴급도']}  {행['보증판정']}")
        except Exception as e:  # 한 건이 실패해도 나머지는 계속 처리
            실패.append((파일.name, e))
            print(f"실패: {파일.name}  {type(e).__name__}: {e}")

    # 2) DB 접수(미처리): 접수일은 발견일
    for 접수 in db.접수_미처리():
        이름 = f"DB접수#{접수['id']}"
        try:
            발견일 = 접수["발견일"] or 접수["접수일시"].date()
            행 = 대장행(접수원문(접수), 이름, 발견일.isoformat(), 공사, 번호)
            행들.append(행)
            완료할_접수.append((접수["id"], 행["접수번호"]))
            print(f"{행['접수번호']}  {이름}  {행['긴급도']}  {행['보증판정']}")
        except Exception as e:
            실패.append((이름, e))
            print(f"실패: {이름}  {type(e).__name__}: {e}")

    db.대장_저장(행들)  # 접수번호가 같으면 덮어쓴다
    for 접수id, 접수번호 in 완료할_접수:  # 대장 저장이 끝난 뒤에만 처리완료로
        db.접수_처리완료(접수id, 접수번호)

    print(f"\n{len(행들)}건 저장 -> DB 하자대장 (DB 접수 {len(완료할_접수)}건 처리완료)"
          + (f" / 실패 {len(실패)}건" if 실패 else ""))
    return 1 if 실패 else 0


if __name__ == "__main__":
    sys.exit(main())
