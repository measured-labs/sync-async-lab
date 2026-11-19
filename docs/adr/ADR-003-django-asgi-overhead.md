# ADR-003: Django ASGI 오버헤드 (A3)

- 상태: 일부만 끝남 — 프로파일링(py-spy)은 하지 않았고, 1차 · A1 처리량 비교로만 판단했다(2026-04-05, 결과 커밋 225438a)
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "A3", [results-extended.md](../archive/report/results-extended.md) "A3", [future-work.md](../archive/report/future-work.md) "A3" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기는 없다. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 선행: [ADR-000](ADR-000-baseline-io-cpu.md) H3 · H4 — Django async-raw와 ORM 경유 async가 거의 같았다.

## 질문

같은 `asyncio.sleep`을 쓰는데 Django ASGI(async-raw)가 FastAPI async보다 훨씬 느린 이유가 Django의 요청 처리 경로(미들웨어 · 요청 객체 생성)에 있는가.

## 선택지

- py-spy로 flamegraph를 떠서 시간을 어디에 쓰는지 직접 본다(계획).
- 이미 잰 처리량(1차 200 VU, A1 1000 VU)으로 차이의 크기만 확인한다(실제로 한 것).

## 실험 설계 · 가설 (원문)

### 가설
**Django ASGI의 병목은 미들웨어 체인과 요청 객체 생성에 있다.**

### 근거
- Django async-raw(269 req/s) vs FastAPI async(735 req/s) → 같은 asyncio.sleep인데 2.7배 차이
- Django는 최소 설정에서도 SecurityMiddleware, SessionMiddleware 등이 기본 로드
- 우리 설정은 INSTALLED_APPS=[]이지만 Django 내부 요청 처리 파이프라인은 여전히 실행

### 예상 결과
- flamegraph에서 Django 내부 요청 처리(WSGIHandler/ASGIHandler)가 시간의 대부분 차지

## 결과 (원문)

> py-spy 프로파일링은 Docker 환경에서 ptrace 권한 이슈로 별도 실행 필요.
> 1차/A1 결과로 정량적 근거는 충분히 확보됨:

- Django async-raw (asyncio.sleep) = 269 req/s (200 VU) / 282 req/s (1000 VU)
- FastAPI async (asyncio.sleep) = 735 req/s (200 VU) / 1558 req/s (1000 VU)
- **같은 asyncio.sleep인데 2.7~5.5배 차이 → Django ASGI 프레임워크 자체의 오버헤드 확정**

## 결정 (결론)

원문은 "같은 asyncio.sleep인데 2.7~5.5배 차이 → Django ASGI 프레임워크 자체의 오버헤드 확정"으로 판정했다.

## 한계

- 원인(미들웨어 체인, 요청 객체 생성 등)을 가리키는 프로파일은 뜨지 않았다. 처리량 차이는 "Django ASGI 경로 어딘가가 느리다"까지만 보여 주고, 가설의 "미들웨어 체인과 요청 객체 생성"이 원인인지는 확인되지 않았다.
- python-django-async-raw의 `/io` 결과는 1차(269.1 req/s) · A1(281.9 req/s) 모두 1회 측정이다.

## 후속 (원문 `future-work.md` "A3: Django ASGI py-spy 프로파일링")

**상태:** Docker ptrace 권한 이슈로 미진행 (정량적 데이터는 확보 완료)

**재시도 방안:**
```bash
# Docker에서 ptrace 허용
docker run --cap-add SYS_PTRACE ...

# 또는 로컬 실행
uvicorn config.asgi:application --port 8005 &
py-spy record -o flamegraph.svg --pid $(pgrep -f uvicorn)
```

**확보된 정량 데이터:**
- Django async-raw vs FastAPI async: 같은 asyncio.sleep인데 2.7배 (200VU) ~ 5.5배 (1000VU) 차이
- Django ASGI 프레임워크 자체의 오버헤드가 원인이라는 결론은 확정
