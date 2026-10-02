# -*- coding: utf-8 -*-
"""
time_loaders.py — 표 읽기 시간을 나눠 잰다: 접속 / 조회 / 파일 읽기.

DB 접속 환경변수를 먼저 설정한다(src/db.py 머리말 참조).
실행: python analysis/time_loaders.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402


def timed(fn):
    s = time.perf_counter()
    out = fn()
    return time.perf_counter() - s, out


print("== 1. DB 접속 시간 (3회) ==")
for i in range(3):
    dt, conn = timed(db._connect)
    conn.close()
    print(f"  {i + 1}회차  {dt:.2f}s")

print("\n== 2. 표별 읽기 (지금 대시보드가 쓰는 방식: 표마다 접속) ==")
total_csv = total_db = 0.0
for name in db.TABLES:
    dc, _ = timed(lambda: db.load(name, source="csv"))
    dd, _ = timed(lambda: db.load(name, source="db"))
    total_csv += dc
    total_db += dd
    print(f"  {name:20s} 파일 {dc:.2f}s | DB(접속 포함) {dd:.2f}s")
print(f"  합계{'':16s} 파일 {total_csv:.2f}s | DB {total_db:.2f}s")

print("\n== 3. 접속 1번으로 5개 표를 읽으면 ==")
schema = os.environ.get("CALLTAXI_DB_SCHEMA", "ADMIN")
t_conn, conn = timed(db._connect)
t_query = 0.0
with conn.cursor() as cur:
    cur.arraysize = 1000
    for name, spec in db.TABLES.items():
        sql = f"SELECT * FROM {schema}.{spec['table']} ORDER BY {spec['order']}"
        dt, rows = timed(lambda: (cur.execute(sql), cur.fetchall())[1])
        t_query += dt
        print(f"  {name:20s} 조회 {dt:.2f}s ({len(rows)}행)")
conn.close()
print(f"  접속 {t_conn:.2f}s + 조회 합계 {t_query:.2f}s = {t_conn + t_query:.2f}s")
