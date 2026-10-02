# -*- coding: utf-8 -*-
"""
check_db_parity.py — 파일로 읽은 표와 DB 로 읽은 표가 같은지 비교한다.

대시보드를 DB 로 옮긴 뒤에도 같은 화면이 나온다는 것을 로더 단위로 확인한다.
합격 기준: 5개 표 전부 '일치'.

실행 (DB 접속 환경변수를 먼저 설정한다 — src/db.py 머리말 참조)
    python analysis/check_db_parity.py

비교 방식: 양쪽을 모든 열로 정렬해 행 순서 차이를 없애고, 숫자는 상대오차 1e-9 안에서
같으면 일치로 본다(파일의 소수 문자열과 DB 숫자가 부동소수 표현에서 1ulp 어긋날 수
있다). 정수/실수 dtype 차이는 값이 같으면 무시한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402


def main() -> int:
    bad = 0
    for name in db.TABLES:
        try:
            a = db.load(name, source="csv")
            b = db.load(name, source="db")
        except Exception as e:                      # 접속·읽기 실패도 불합격이다
            bad += 1
            print(f"{name:20s} 읽기 실패: {type(e).__name__}: {str(e)[:200]}")
            continue
        if list(a.columns) != list(b.columns):
            bad += 1
            only_a = [c for c in a.columns if c not in b.columns]
            only_b = [c for c in b.columns if c not in a.columns]
            print(f"{name:20s} 열 불일치  파일에만 {only_a} / DB에만 {only_b}")
            continue
        a = a.sort_values(list(a.columns)).reset_index(drop=True)
        b = b.sort_values(list(b.columns)).reset_index(drop=True)
        try:
            pd.testing.assert_frame_equal(
                a, b, check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-12)
            print(f"{name:20s} 일치  ({len(a)}행 x {a.shape[1]}열)")
        except AssertionError as e:
            bad += 1
            print(f"{name:20s} 불일치  {str(e).splitlines()[0][:200]}")
    print("결과:", "모두 일치" if bad == 0 else f"{bad}개 표 확인 필요")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
