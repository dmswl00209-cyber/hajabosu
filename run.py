"""접수함 폴더의 원문을 모두 처리해 하자대장 CSV로 저장한다.
흐름: 원문 -> ai.접수정리(AI가 읽는 칸) -> rules(번호·기한·판정) -> CSV"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import ai
import rules

BASE = Path(__file__).parent
접수함 = BASE / "data" / "접수함"
출력 = BASE / "data" / "하자대장.csv"

칸 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
      "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]


def 파일명_날짜(파일명: str) -> str | None:
    """'01_20261102_...' -> '2026-11-02'. 접수일이 원문에 없을 때만 쓴다."""
    m = re.match(r"^\d+_(\d{4})(\d{2})(\d{2})_", 파일명)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def main() -> int:
    공사 = rules.공사정보_읽기()
    순번 = defaultdict(int)  # 접수일별 순번
    행들, 실패 = [], []

    for 파일 in sorted(접수함.glob("*.txt")):
        try:
            결과 = ai.접수정리(파일.read_text(encoding="utf-8"))
            접수일 = 결과.get("접수일") or 파일명_날짜(파일.name)
            if not 접수일:
                raise ValueError("접수일을 원문과 파일명 어디에서도 찾지 못했습니다.")
            순번[접수일] += 1
            긴급 = rules.긴급도(결과["긴급근거"])
            판정 = rules.보증판정(접수일, 결과["위치"], 결과["공종"], 공사)
            행 = {
                "접수번호": rules.접수번호(접수일, 순번[접수일]),
                "접수일": 접수일,
                "원문파일": 파일.name,
                "위치": 결과["위치"],
                "공종": 결과["공종"],
                "하자내용": 결과["하자내용"],
                "긴급도": 긴급,
                "조치기한": rules.조치기한(접수일, 긴급).isoformat(),
                **판정,
                "상태": "확인필요" if 판정["보증판정"] == "확인필요" else "판정완료",
            }
            if len(행["하자내용"]) > 40:
                print(f"  주의: {파일.name} 하자내용이 40자를 넘습니다({len(행['하자내용'])}자).")
            행들.append(행)
            print(f"{행['접수번호']}  {파일.name}  {행['긴급도']}  {행['보증판정']}")
        except Exception as e:  # 한 건이 실패해도 나머지는 계속 처리
            실패.append((파일.name, e))
            print(f"실패: {파일.name}  {type(e).__name__}: {e}")

    with open(출력, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        w = csv.DictWriter(f, fieldnames=칸)
        w.writeheader()
        w.writerows(행들)

    print(f"\n{len(행들)}건 저장 -> {출력}" + (f" / 실패 {len(실패)}건" if 실패 else ""))
    return 1 if 실패 else 0


if __name__ == "__main__":
    sys.exit(main())
