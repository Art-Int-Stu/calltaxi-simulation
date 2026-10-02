# -*- coding: utf-8 -*-
"""
db.py — 결과 표 읽기. 파일(CSV·parquet) 또는 Oracle Autonomous DB.

환경변수 CALLTAXI_SOURCE 가 "db" 이면 DB 에서, 그 밖(기본)에는 outputs/ 의 파일에서
읽는다. 기본을 파일로 둔 것은 기존 로컬 실행과 테스트를 그대로 지키기 위해서다.

**DB 모드에서 접속이 실패하면 파일로 물러나지 않고 그대로 실패한다.** 조용히 다른
출처로 바꾸면 화면이 어느 데이터를 보여주는지 알 수 없게 된다.

DB 접속 정보는 코드가 아니라 환경변수로만 받는다(저장소에 넣지 않는다).
  CALLTAXI_DB_USER  CALLTAXI_DB_PASSWORD  CALLTAXI_DB_DSN(접속 별칭)
  CALLTAXI_WALLET_DIR  CALLTAXI_WALLET_PASSWORD  [CALLTAXI_DB_SCHEMA, 기본 ADMIN]

DB 표는 CSV 를 그대로 적재한 것이라 **읽고 나서 원래 형태로 되돌리는 처리**가 필요하다:
  · Oracle 은 컬럼명을 대문자로 돌려준다 → 소문자
  · 참/거짓 컬럼은 'True'/'False' 문자열로 적재돼 있다 → bool
  · 예약어 충돌로 이름을 바꿔 적재한 컬럼(interval → interval_text) → 원래 이름
  · DB 는 행 순서를 보장하지 않는다 → 자연키로 ORDER BY
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"

# name → 설정. order 는 DB 에서 읽을 때의 정렬 키(자연키)다.
TABLES = {
    "dong_metrics": dict(
        table="DONG_METRICS", file="dong_metrics.csv",
        order="gu, dong, dong_canon", bools=("is_reliable", "usage_is_grouped")),
    "dong_candidates": dict(
        table="DONG_CANDIDATES", file="dong_candidates.csv",
        order="adm_cd2", bools=("is_assigned", "cand_beyond_cap")),
    "placement_grades": dict(
        table="PLACEMENT_GRADES", file="placement_grades.csv",
        order="cand_id", bools=("sample_ok",),
        rename={"interval_text": "interval"}),
    "placement_eval": dict(
        table="PLACEMENT_EVAL", file="placement_eval.csv",
        order="cand_id, seed", bools=()),
    "dong_demand_matrix": dict(
        table="DONG_DEMAND_MATRIX", file="dong_demand_matrix.parquet",
        order="gu, dong_canon, period, is_weekend", bools=("is_weekend",)),
}

_ENV = ["CALLTAXI_DB_USER", "CALLTAXI_DB_PASSWORD", "CALLTAXI_DB_DSN",
        "CALLTAXI_WALLET_DIR", "CALLTAXI_WALLET_PASSWORD"]


def source() -> str:
    return os.environ.get("CALLTAXI_SOURCE", "csv").strip().lower()


def is_db() -> bool:
    return source() == "db"


def available(name: str) -> bool:
    """이 표를 읽을 수 있는가. DB 모드에서는 있다고 본다(없으면 읽을 때 실패한다)."""
    if is_db():
        return True
    return (OUTPUTS / TABLES[name]["file"]).exists()


_POOL = None
_POOL_LOCK = threading.Lock()


def _get_pool():
    """커넥션 풀 — 프로세스에서 한 번만 만든다.

    표마다 접속을 새로 열면 접속 비용(지갑 인증, 0.3~0.5초)이 표 수만큼 붙는다.
    풀은 한 번 맺은 접속을 돌려 쓴다. 웹 앱은 요청이 여러 스레드에서 오므로 접속 하나를
    공유하지 않고 풀에서 빌려 쓰고 돌려주는 방식이 맞다(풀은 스레드 안전하다).
    """
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:                       # 락을 기다리는 사이 다른 스레드가 만들었을 수 있다
                import oracledb                     # 지연 임포트 — 파일 모드에서는 필요 없다
                missing = [k for k in _ENV if not os.environ.get(k)]
                if missing:
                    raise RuntimeError("DB 접속 환경변수가 없다: " + ", ".join(missing))
                wallet = os.environ["CALLTAXI_WALLET_DIR"]
                _POOL = oracledb.create_pool(
                    user=os.environ["CALLTAXI_DB_USER"],
                    password=os.environ["CALLTAXI_DB_PASSWORD"],
                    dsn=os.environ["CALLTAXI_DB_DSN"],
                    config_dir=wallet, wallet_location=wallet,
                    wallet_password=os.environ["CALLTAXI_WALLET_PASSWORD"],
                    min=1, max=4, increment=1)
    return _POOL


def _connect():
    """풀에서 접속을 빌린다. 풀 접속의 close() 는 끊지 않고 풀에 돌려준다."""
    return _get_pool().acquire()


def _read_file(spec: dict) -> pd.DataFrame:
    path = OUTPUTS / spec["file"]
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_db(spec: dict) -> pd.DataFrame:
    schema = os.environ.get("CALLTAXI_DB_SCHEMA", "ADMIN")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.arraysize = 1000
            cur.execute(f"SELECT * FROM {schema}.{spec['table']} ORDER BY {spec['order']}")
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()
    return normalize(pd.DataFrame(rows, columns=cols), spec)


def normalize(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """DB 에서 읽은 표를 파일에서 읽은 것과 같은 형태로 되돌린다."""
    df = df.rename(columns=spec.get("rename", {})).copy()
    for c in spec.get("bools", ()):
        mapped = df[c].map({"True": True, "False": False})
        if mapped.isna().any():
            bad = df.loc[mapped.isna(), c].unique()[:5]
            raise ValueError(f"{spec['table']}.{c}: True/False 가 아닌 값 {list(bad)}")
        df[c] = mapped.astype(bool)
    for c in df.columns:
        if df[c].dtype == object:
            nn = df[c].dropna()
            if len(nn) and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                               for v in nn):
                df[c] = pd.to_numeric(df[c])          # 값이 전부 NULL 아닌 숫자인 열
            else:
                df[c] = df[c].where(df[c].notna(), np.nan)   # None → NaN(파일과 같게)
    return df.reset_index(drop=True)


def load(name: str, source: str | None = None) -> pd.DataFrame:
    """표 하나를 읽는다. source 를 주면 환경변수를 무시하고 그쪽으로 읽는다(비교용)."""
    spec = TABLES[name]
    use_db = (source or globals()["source"]()) == "db"
    return _read_db(spec) if use_db else _read_file(spec)
