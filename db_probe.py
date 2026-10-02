"""db_probe.py — 지갑(tnsnames.ora)의 접속 별칭을 전부 시도해 결과를 비교한다.

목적: 어떤 별칭이 되고 어떤 별칭이 거부되는지, 에러가 어느 계층에서 나는지 좁힌다.
비밀번호는 getpass 로만 받고 출력하지 않는다. 실행: python db_probe.py
"""
import getpass
import os
import re
import sys

import oracledb

wallet_dir = input("지갑 폴더 경로: ").strip().strip('"')
user = input("사용자 [DASH_READER]: ").strip() or "DASH_READER"
password = getpass.getpass("사용자 비밀번호: ")
wallet_password = getpass.getpass("지갑 비밀번호: ")

tns_path = os.path.join(wallet_dir, "tnsnames.ora")
try:
    text = open(tns_path, encoding="utf-8", errors="replace").read()
except OSError as e:
    print("tnsnames.ora 를 읽을 수 없음:", e)
    sys.exit(1)

aliases = re.findall(r"^([A-Za-z0-9_.\-]+)\s*=\s*\(", text, flags=re.M)
print(f"드라이버 {oracledb.__version__} | 별칭 {len(aliases)}개: {aliases}\n")

for alias in aliases:
    try:
        conn = oracledb.connect(
            user=user, password=password, dsn=alias,
            config_dir=wallet_dir, wallet_location=wallet_dir,
            wallet_password=wallet_password, tcp_connect_timeout=10,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dual")
            cur.fetchone()
        conn.close()
        print(f"{alias:28s} 성공")
    except oracledb.Error as e:
        msg = str(e).splitlines()
        print(f"{alias:28s} 실패 | {' / '.join(m.strip() for m in msg[:2])[:150]}")
