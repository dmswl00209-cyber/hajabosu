"""저장은 이 파일에서만 한다. 연결 정보는 .env의 DATABASE_URL (웹 배포는 Streamlit Secrets).
처음 쓸 때 테이블 2개(접수, 하자대장)를 만들고 둘 다 RLS(행 수준 보안)를 켠다."""
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent / ".env")

# data/하자대장.csv와 같은 열, 같은 순서
대장_칸 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
         "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]
_날짜_칸 = {"접수일", "조치기한", "준공일", "보증만료일"}

_테이블_만들기 = [
    """
    CREATE TABLE IF NOT EXISTS "접수" (
        "id"       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        "접수일시"  TIMESTAMPTZ NOT NULL DEFAULT now(),
        "발견일"    DATE,
        "접수자"    TEXT,
        "부서"      TEXT,
        "위치"      TEXT,
        "내용"      TEXT,
        "처리상태"  TEXT NOT NULL DEFAULT '미처리' CHECK ("처리상태" IN ('미처리', '처리완료')),
        "접수번호"  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "하자대장" (
        "접수번호"   TEXT PRIMARY KEY,
        "접수일"     DATE,
        "원문파일"   TEXT,
        "위치"       TEXT,
        "공종"       TEXT,
        "하자내용"   TEXT,
        "긴급도"     TEXT,
        "조치기한"   DATE,
        "공사번호"   TEXT,
        "시공업체"   TEXT,
        "준공일"     DATE,
        "보증만료일" DATE,
        "보증판정"   TEXT,
        "책임구분"   TEXT,
        "상태"       TEXT,
        "비고"       TEXT
    )
    """,
    'ALTER TABLE "접수" ENABLE ROW LEVEL SECURITY',
    'ALTER TABLE "하자대장" ENABLE ROW LEVEL SECURITY',
]

_engine = None


def _url() -> str:
    주소 = os.getenv("DATABASE_URL", "").strip()
    if not 주소:
        raise RuntimeError(".env에 DATABASE_URL이 없습니다.")
    # SQLAlchemy가 psycopg(v3)를 쓰도록 접두어를 맞춘다
    for 앞 in ("postgresql://", "postgres://"):
        if 주소.startswith(앞):
            return "postgresql+psycopg://" + 주소[len(앞):]
    return 주소


def engine():
    """엔진을 만들고, 처음 한 번 테이블을 준비한다."""
    global _engine
    if _engine is None:
        e = create_engine(_url(), pool_pre_ping=True)
        with e.begin() as conn:
            for 문장 in _테이블_만들기:
                conn.execute(text(문장))
        _engine = e
    return _engine


def _값(칸: str, v):
    """CSV 글자 -> DB 값. 날짜 칸의 빈 값은 NULL."""
    v = "" if v is None else str(v)
    if 칸 in _날짜_칸:
        v = v.strip()
        return date.fromisoformat(v) if v else None
    return v


def 대장_저장(행들: list[dict]) -> int:
    """하자대장에 넣는다. 접수번호가 같으면 덮어쓰고, 없는 행은 그대로 둔다."""
    if not 행들:
        return 0
    칸목록 = ", ".join(f'"{c}"' for c in 대장_칸)
    값목록 = ", ".join(f":{i}" for i in range(len(대장_칸)))
    갱신 = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in 대장_칸 if c != "접수번호")
    문장 = text(f'INSERT INTO "하자대장" ({칸목록}) VALUES ({값목록}) '
              f'ON CONFLICT ("접수번호") DO UPDATE SET {갱신}')
    with engine().begin() as conn:
        for 행 in 행들:
            conn.execute(문장, {str(i): _값(c, 행.get(c)) for i, c in enumerate(대장_칸)})
    return len(행들)


def 대장_읽기() -> list[dict]:
    """하자대장 전체를 접수번호 순으로. 값은 CSV와 같은 글자(날짜는 YYYY-MM-DD, 빈 값은 빈 글자)."""
    칸목록 = ", ".join(f'"{c}"' for c in 대장_칸)
    with engine().connect() as conn:
        rows = conn.execute(text(f'SELECT {칸목록} FROM "하자대장" ORDER BY "접수번호"')).all()
    def 글(v):
        return "" if v is None else v.isoformat() if isinstance(v, (date, datetime)) else str(v)
    return [{c: 글(v) for c, v in zip(대장_칸, r)} for r in rows]


def 건수() -> dict:
    """테이블별 건수."""
    with engine().connect() as conn:
        return {t: conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in ("접수", "하자대장")}
