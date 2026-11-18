# ADR-004: Python CPU-bound — ProcessPoolExecutor로 GIL 우회 (B1)

- 상태: 끝남 — 2026-04-05 Docker에서 실패(행), 2026-04-10 Docker 밖 로컬에서 다시 측정(결과 커밋 342ecff, 2026-04-11)
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "B1", [results-extended.md](../archive/report/results-extended.md) "B1", [future-work.md](../archive/report/future-work.md) "B1" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 원문 판정(원문 절 제목): "B1: Python ProcessPoolExecutor CPU-bound — ⚠️ 부분 입증 (1.33x, 가설 2x 미달)"
- 줄임 이름: B1은 확장 실험 목록 B(새 서버 · 설정이 필요한 실험)의 첫 항목이다.
- 선행: [ADR-000](ADR-000-baseline-io-cpu.md) H2 — Python CPU-bound는 GIL 때문에 약 1 req/s.

## 질문

FastAPI async에서 fibonacci(38)을 `ProcessPoolExecutor`(워커 2개)로 보내면, GIL을 우회해 2코어만큼(2배) 처리량이 오르는가.

## 선택지

| 엔드포인트 | 방식 |
|---|---|
| `GET /cpu` | 이벤트 루프 안에서 바로 계산(블로킹) |
| `GET /cpu-mp` | `loop.run_in_executor(ProcessPoolExecutor(2), fibonacci, 38)` |

## 실험 설계 · 가설 (원문)

### 가설
**ProcessPoolExecutor를 사용하면 Python CPU-bound 성능이 코어 수에 비례하여 향상될 것이다 (1 req/s → 2 req/s).**

### 근거
- 1차 결과: Python CPU ~1 req/s (GIL → 싱글코어)
- ProcessPoolExecutor는 별도 프로세스에서 실행 → GIL 우회
- 2코어 환경이므로 최대 2배 향상 예상

첫 시도(2026-04-05, Docker)의 상태 — 원문 `future-work.md`:

**상태:** Docker + uvicorn 환경에서 fork 충돌로 실패

**문제:**
- `ProcessPoolExecutor`가 uvicorn 워커 프로세스 내에서 서브프로세스를 fork할 때 충돌 발생
- 단일 요청은 성공하지만, 동시 요청 시 행(hang) 발생
- startup 이벤트로 초기화 위치를 옮겨도 Docker 컨테이너 환경에서 동일 문제

**재시도 방안:**
1. Docker 외부(로컬)에서 직접 실행하여 fork 충돌 확인
2. `multiprocessing.set_start_method('spawn')` 설정 후 테스트
3. uvicorn `--workers 1` + ProcessPoolExecutor vs `--workers 2` 비교
4. Celery 등 외부 워커 프로세스로 CPU 작업 위임하는 구조 테스트

**기대 결과:** GIL 우회 시 2코어 환경에서 ~2 req/s (기존 ~1 req/s의 2배)

## 결과 (원문)

> 재실험일: 2026-04-10
> 환경: 로컬 직접 실행 (Docker 외부), i7-13700HX 24코어 (절전 모드 ~1200MHz)
> k6 서버(별도 PC) → 앱 서버 :8002

### 이전 실패

- Docker + uvicorn 환경에서 `ProcessPoolExecutor`가 동시 요청 시 행(hang) 발생
- 원인: uvicorn 워커 프로세스 내부에서 `fork()` 시 자식 프로세스가 부모의 락/소켓 상태를 상속하면서 교착 상태 발생
- Docker의 PID namespace 격리 + uvicorn의 프로세스 매니저가 fork 충돌을 악화시킨 것으로 추정

### 로컬 재실험

Docker를 우회하여 로컬에서 직접 `uvicorn main:app --host 0.0.0.0 --port 8002 --workers 1`로 실행.
DB 연결 없이 `/cpu`와 `/cpu-mp` 엔드포인트만 테스트.

**단일 요청 확인:**
- `/cpu`: fibonacci(38) = 39088169, ~7.1초 (이벤트 루프 블로킹)
- `/cpu-mp`: fibonacci(38) = 39088169, ~7.4초 (ProcessPoolExecutor 경유)
- 동시 5개 요청: 모두 성공 — Docker에서 발생했던 hang 재현 안 됨

### k6 부하 테스트 결과

| 엔드포인트 | 방식 | VU | duration | req/s | total | avg | min | med | p95 |
|-----------|------|---:|--------:|------:|------:|----:|----:|----:|----:|
| `/cpu` | 이벤트 루프 블로킹 | 10 | 60s | 0.133 | 12 | 44.67s | 7.51s | 46.71s | 1m10s |
| `/cpu-mp` | ProcessPoolExecutor(2) | 10 | 60s | 0.178 | 16 | 44.57s | 33.79s | 39.54s | 1m3s |

**처리량 비교: 0.133 → 0.178 req/s = 1.33배 향상 (가설 2배 미달)**

### 가설 미달 원인 분석

가설은 "2코어이므로 2배"였으나 실제 1.33배에 그친 이유는 3가지다.

#### 1. IPC 오버헤드 (Inter-Process Communication)

ProcessPoolExecutor는 메인 프로세스와 워커 프로세스 사이에서 데이터를 주고받을 때
**pickle 직렬화 → 파이프 전송 → pickle 역직렬화** 과정을 거친다.

```
[메인 프로세스 (이벤트 루프)]
    │
    ├─ pickle.dumps(fibonacci, 38)  ← 함수+인자 직렬화
    ├─ pipe.write(data)             ← OS 파이프로 전송
    │
    ▼
[워커 프로세스 1]
    ├─ pipe.read(data)              ← 수신
    ├─ pickle.loads(data)           ← 역직렬화
    ├─ fibonacci(38) 실행           ← 실제 연산 (~7초)
    ├─ pickle.dumps(result)         ← 결과 직렬화
    └─ pipe.write(result)           ← 결과 전송
    │
    ▼
[메인 프로세스]
    ├─ pipe.read(result)            ← 결과 수신
    └─ pickle.loads(result)         ← 결과 역직렬화
```

각 요청마다 이 왕복 직렬화가 발생한다. fibonacci(38)은 단순 정수 반환이라 직렬화 비용은 작지만,
**파이프 I/O + 프로세스 스케줄링 전환(context switch)** 비용이 요청당 수~수십 ms 추가된다.
10 VU × 60초 동안 누적되면 유효 처리 시간의 일부를 소모한다.

#### 2. 이벤트 루프 직렬화 (Event Loop Serialization)

`/cpu-mp`의 코드 흐름을 자세히 보면:

```python
@app.get("/cpu-mp")
async def cpu_mp_endpoint():
    loop = asyncio.get_event_loop()                          # ①
    result = await loop.run_in_executor(process_pool, fibonacci, 38)  # ②
    return {"server": "fastapi-async", "type": "cpu-mp", "fibonacci": result}  # ③
```

fibonacci(38) 자체는 워커 프로세스에서 **병렬** 실행된다. 하지만:

- **① 요청 수신/파싱**: HTTP 파싱, 라우팅, 핸들러 디스패치 — **이벤트 루프에서 순차 처리**
- **③ 응답 직렬화/전송**: JSON 직렬화, HTTP 응답 구성, 소켓 write — **이벤트 루프에서 순차 처리**

즉, 요청 파이프라인 전체가 아래처럼 동작한다:

```
시간 →

이벤트 루프:  [req1 수신] [req2 수신] .......... [req1 응답] [req2 응답] [req3 수신]...
                 │           │                       ▲           ▲
                 ▼           ▼                       │           │
워커 프로세스1:   [───── fibonacci(38) ─────]─────────┘           │
워커 프로세스2:       [───── fibonacci(38) ─────]────────────────┘
```

fibonacci(38)이 병렬로 돌아도, **응답 직렬화는 이벤트 루프에서 하나씩 처리**된다.
요청이 많아질수록 이벤트 루프가 응답 처리에 바빠져서 새 요청 수신이 밀린다.
이것이 "2개 워커를 풀로 써도 2배에 못 미치는" 구조적 원인이다.

#### 3. CPU 주파수 스케일링 (CPU Frequency Scaling)

테스트 환경의 CPU(i7-13700HX)가 절전 모드(governor: powersave)로 동작 중이었다:

```
최대 MHz: 5000
최소 MHz: 800
테스트 시 스케일링: ~24% (약 1200MHz)
```

싱글코어 부하(1개 워커)에서는 CPU가 해당 코어만 부스트할 수 있지만,
멀티코어 부하(2개 워커 동시 실행)에서는 **발열/전력 제약으로 부스트 클럭이 낮아진다.**
이것은 "코어 수 × 2 = 처리량 × 2"가 성립하지 않는 하드웨어 수준의 원인이다.

특히 Intel의 P-core / E-core 혼합 아키텍처(13세대)에서는 워커 프로세스가
E-core에 스케줄링될 경우 P-core 대비 성능이 크게 떨어질 수 있다.

### Docker vs 로컬 차이 원인

| 항목 | Docker (실패) | 로컬 (성공) |
|------|:------------:|:----------:|
| fork() 환경 | PID namespace 격리 + uvicorn 프로세스 매니저 | 표준 리눅스 fork |
| 공유 자원 충돌 | 컨테이너 내 소켓/파일 디스크립터 상속 문제 | 없음 |
| cgroup 제약 | cpus: 2.0 (CPU 시간 제한) | 24코어 자유 |
| 동시 요청 | 행(hang) 발생 | 정상 처리 |

Docker에서의 fork 실패는 **cgroup v2의 CPU 제한 + PID namespace** 환경에서
`ProcessPoolExecutor`의 자식 프로세스가 부모의 리소스 제한/소켓 상태를 상속하면서
교착 상태에 빠지는 것으로 추정된다. `multiprocessing.set_start_method('spawn')`으로
우회 가능할 수 있으나, 이번 실험에서는 로컬 실행으로 문제를 회피했다.

### 결론

| 항목 | 값 |
|------|---:|
| 가설 | 2x 향상 |
| 실측 | **1.33x 향상** |
| 가설 판정 | ⚠️ 부분 입증 |

- ProcessPoolExecutor는 GIL을 우회하여 CPU-bound 성능을 향상시킨다 → **맞음**
- 그러나 코어 수에 비례하는 선형 확장은 달성되지 않음 → **IPC + 이벤트 루프 직렬화 + CPU 스케일링이 병목**
- Docker 환경에서의 fork 문제는 별도의 실행 환경 구성이 필요 → `spawn` 모드 또는 Celery 같은 외부 워커 구조가 프로덕션에 적합

## 결정 (결론)

ProcessPoolExecutor는 GIL을 우회해 CPU-bound 처리량을 올린다(0.133 → 0.178 req/s, 1.33배). 다만 2배에는 못 미쳤고, 원문은 그 원인을 IPC 비용 · 이벤트 루프의 요청 · 응답 처리 · CPU 절전 모드로 봤다. Docker 안에서의 fork 문제는 `spawn` 시작 방식이나 Celery 같은 외부 워커로 풀어야 한다고 적었다.

## 한계

- 측정 환경이 다른 실험과 다르다. Docker의 2 CPU 제한 없이 로컬(i7-13700HX 24코어, 절전 모드 ~1200MHz)에서 직접 실행했고, VU도 10이다. 다른 ADR의 Python CPU 수치와 그대로 비교할 수 없다.
- 1회 측정, 요청 수가 12건 · 16건으로 적다.
- 미달 원인 세 가지(IPC · 이벤트 루프 · CPU 주파수)는 각각 따로 재지 않은 추정이다.
- 2026-11-18 확인: k6 원본 `k6/results/extended-20260405/`의 2026-04-05 측정분(날짜로 보아 Docker 시도)에서 `fastapi-async-cpu-mp.json`(100 VU)은 요청 154건 중 144건(93.5%)이, `fastapi-async-cpu-mp-10vu.json`(10 VU)은 10건 모두 실패했다. 위 원문의 "이전 실패"(Docker에서 행)와 맞는다. 로컬 재실험의 원본 출력은 저장소에 없다.
