"""AI 호출은 이 파일에서만 한다. 키와 모델은 .env에서 읽는다."""
import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

MODEL = os.getenv("MODEL", "claude-haiku-5-5")
지침_폴더 = BASE / "지침"


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(".env에 ANTHROPIC_API_KEY가 없습니다.")
    return anthropic.Anthropic()  # 키는 환경변수(.env에서 읽은 값)로 자동 사용


def _json_추출(글: str) -> dict:
    """AI 답에서 JSON 객체 하나를 꺼낸다. 코드 블록이 붙어 와도 처리한다."""
    글 = 글.strip()
    글 = re.sub(r"^```(?:json)?\s*|\s*```$", "", 글)
    return json.loads(글)


def 접수정리(원문: str) -> dict:
    """접수 원문 1건 -> 하자대장 칸 JSON(dict). 지침/접수정리.md를 시스템 프롬프트로 쓴다."""
    지침 = (지침_폴더 / "접수정리.md").read_text(encoding="utf-8")
    응답 = _client().messages.create(
        model=MODEL,
        max_tokens=4000,
        system=지침,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": 원문}],
    )
    if 응답.stop_reason != "end_turn":
        raise RuntimeError(f"AI 응답이 정상 종료되지 않았습니다: {응답.stop_reason}")
    글 = "".join(b.text for b in 응답.content if b.type == "text")
    return _json_추출(글)
