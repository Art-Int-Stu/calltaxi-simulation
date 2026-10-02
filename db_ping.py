"""db_ping.py — Autonomous DB 접속·읽기 권한 점검 (thin 모드, 지갑 사용)

비밀번호는 코드·명령줄이 아니라 입력창(getpass)으로만 받는다.
실행: python db_ping.py
"""
import getpass
import sys

import oracledb

TABLES = {
    "DONG_METRICS": 432,
    "DONG_CANDIDATES": 426,
    "PLACEMENT_GRADES": 244,
    "PLACEMENT_EVAL": 732,
    "DONG_DEMAND_MATRIX": 3413,
}

wallet_dir = input("지갑 폴더 경로: ").strip().strip('"')
dsn = input("접속 별칭 [calltaxidb_low]: ").strip() or "calltaxidb_low"
user = input("사용자 [DASH_READER]: ").strip() or "DASH_READER"
password = getpass.getpass("사용자 비밀번호: ")
wallet_password = getpass.getpass("지갑 비밀번호: ")

try:
    conn = oracledb.connect(
        user=user,
        password=password,
        dsn=dsn,
        config_dir=wallet_dir,
        wallet_location=wallet_dir,
        wallet_password=wallet_password,
    )
except oracledb.Error as e:
    print("접속 실패:", e)
    sys.exit(1)

print(f"접속 성공 | thin 모드: {conn.thin} | 드라이버 {oracledb.__version__}")

bad = 0
with conn.cursor() as cur:
    for table, expect in TABLES.items():
        try:
            cur.execute(f"SELECT COUNT(*) FROM ADMIN.{table}")
            n = cur.fetchone()[0]
            ok = "OK" if n == expect else "불일치"
            bad += n != expect
            print(f"{table:20s} {n:6d}  (기대 {expect})  {ok}")
        except oracledb.Error as e:
            bad += 1
            print(f"{table:20s} 조회 실패: {e}")

conn.close()
print("결과:", "모두 통과" if bad == 0 else f"{bad}건 확인 필요")
