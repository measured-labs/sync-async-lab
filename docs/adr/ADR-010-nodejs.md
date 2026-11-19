# ADR-010: Node.js Express 추가 (B5)

- 상태: 끝남 — 2026-04-05 측정 · 결과 커밋 225438a
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "B5", [results-extended.md](../archive/report/results-extended.md) "B5" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기는 없다. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 줄임 이름: B5는 확장 실험 목록 B의 다섯째 항목이다.

## 질문

같은 싱글 스레드 이벤트 루프 모델인 Node.js(Express)는 FastAPI async와 비슷하게 동작하는가.

## 선택지

node-server(포트 8010)를 ADR-000 · ADR-002와 같은 `/io`(200 VU) · `/cpu`(100 VU) · `/db`(200 VU) 시나리오로 잰다.

## 가설 (원문)

### 가설
**Node.js는 I/O-bound에서 FastAPI async와 비슷한 수준이고, CPU-bound에서 Python과 비슷하게 낮을 것이다.**

### 근거
- 같은 싱글 스레드 이벤트 루프 모델
- V8 엔진이 CPython보다 빠르지만 싱글 스레드 한계는 동일

## 결과 (원문)

### I/O-bound (200 VU)
| 메트릭 | 값 |
|--------|---:|
| req/s | 740.4 |
| avg | 202.9ms |
| p95 | 206.4ms |
| total | 88,870 |

### CPU-bound (100 VU)
- 1.9 req/s (싱글 스레드 이벤트 루프 블로킹)

### DB-bound (200 VU)
- 3.3 req/s (심한 큐잉 — pg Pool 20 + 싱글 스레드)

### 가설 검증: ✅ 부분 입증

- I/O: 740 req/s — **FastAPI async(735)와 거의 동일** (같은 이벤트 루프 모델)
- CPU: 1.9 req/s — Python(1.0)보다 약간 빠름 (V8 > CPython). 하지만 Java/Go의 2.5 req/s보다 낮음.
- DB: 심각하게 느림 — 싱글 스레드가 커넥션 풀 대기를 블로킹

## 결정 (결론)

I/O-bound에서는 FastAPI async와 거의 같았다(740.4 vs 735.6 req/s). 원문은 같은 이벤트 루프 모델이라 성능도 같다고 판정했다.

## 한계

- 1회 측정.
- 2026-11-18 확인: k6 원본 `k6/results/extended-20260405/`에서 `node-cpu.json`은 요청 274건 중 131건(47.8%), `node-db.json`은 398건 중 200건(50.3%)이 실패했다. CPU 1.9 req/s · DB 3.3 req/s는 실패를 포함한 값이다. `node-io.json`은 실패 0건이다. 원문 수치는 고치지 않았다.
- DB-bound가 3.3 req/s로 다른 서버(약 95 req/s, [ADR-002](ADR-002-db-io-connection-pool.md))보다 크게 낮은 이유를 원문은 "싱글 스레드가 커넥션 풀 대기를 블로킹"으로 적었지만, 코드로 확인하지 않았다.
