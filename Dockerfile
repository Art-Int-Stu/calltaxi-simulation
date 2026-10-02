# 장애인콜택시 대기 진단 대시보드 — 컨테이너 이미지
#
# 지갑·비밀번호는 이미지에 넣지 않는다. 실행할 때 넘긴다:
#   지갑 폴더  → 볼륨으로 /wallet 에 읽기 전용 마운트
#   비밀번호   → 환경변수(CALLTAXI_DB_PASSWORD, CALLTAXI_WALLET_PASSWORD)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CALLTAXI_SOURCE=db \
    CALLTAXI_WALLET_DIR=/wallet \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# 라이브러리를 먼저 설치한다 — 코드만 바뀌면 이 층은 캐시를 재사용한다.
# 컴파일러는 넣지 않는다: 모든 라이브러리가 사전 빌드 휠로 설치돼야 하고, 소스 빌드가
# 필요해지면 빌드가 실패해 알려준다(이미지가 작아지고 공격 표면이 준다).
COPY requirements-app.txt .
RUN pip install --no-cache-dir --prefer-binary --default-timeout=100 --retries=5 -r requirements-app.txt

# 코드와 저장소 동봉 자료(outputs/·data/ 는 넣지 않는다 — 결과는 DB 에서 읽는다)
COPY src/ src/
COPY assets/ assets/

# 루트로 돌리지 않는다
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

CMD ["streamlit", "run", "src/dashboard.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
