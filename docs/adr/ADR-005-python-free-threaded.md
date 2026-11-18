# ADR-005: Python 3.13 free-threaded(no-GIL)의 ThreadPoolExecutor 병렬화 (#1)

- 상태: 끝남 — 2026-04-11 측정 · 결과 커밋 def78ff
- 원문: [results-extended.md](../archive/report/results-extended.md) "#1", [future-work.md](../archive/report/future-work.md) "#1 Python 3.13 free-threaded" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로; 끝의 경로 `report/results-extended.md` → `docs/archive/report/results-extended.md`. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 원문 판정(원문 절 제목): "#1: Python 3.13 Free-Threaded (PEP 703, No-GIL) — ✅ 입증 (ThreadPoolExecutor로 진짜 CPU 병렬)"
- 줄임 이름: #1은 [future-work.md](../archive/report/future-work.md) "추가 확장 가능 주제" 표의 1번이다.
- 선행: [ADR-004](ADR-004-python-processpool.md) — ProcessPoolExecutor는 1.33배에 그쳤다.

## 질문

GIL을 끈 CPython 3.13 빌드에서는 `ThreadPoolExecutor`(워커 2개)만으로 CPU-bound 작업을 실제로 병렬 실행해 처리량을 2배로 올릴 수 있는가.

## 선택지

| 엔드포인트 | 방식 |
|---|---|
| `GET /cpu` | free-threaded 빌드, 이벤트 루프 안에서 바로 계산 |
| `GET /cpu-mt` | free-threaded 빌드, `ThreadPoolExecutor(max_workers=2)` |

비교 참고: ADR-004의 ProcessPoolExecutor(GIL 있는 표준 빌드).

## 실험 설계 · 결과 (원문)

> 실험일: 2026-04-11
> 환경: Docker (2 CPU, 512MB RAM), Python 3.13.13 free-threading build (--disable-gil)
> k6 서버(별도 PC) → 앱 서버 :8012

### 가설

GIL이 제거된 Python에서 ThreadPoolExecutor(2)를 사용하면, IPC 오버헤드 없이
CPU-bound 작업을 진짜 병렬 실행하여 처리량이 2배 향상될 것이다.

### 수행한 작업

#### CPython 3.13 --disable-gil 소스 빌드

공식 Docker 이미지에 free-threaded 빌드가 없어, 소스에서 직접 빌드:

```dockerfile
FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y build-essential zlib1g-dev libffi-dev libssl-dev ...
ARG PYTHON_VERSION=3.13.13
RUN wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
    && tar xzf Python-${PYTHON_VERSION}.tgz \
    && cd Python-${PYTHON_VERSION} \
    && ./configure --prefix=/opt/python-freethreaded --disable-gil --enable-optimizations --with-lto \
    && make -j$(nproc) && make install
```

- `--disable-gil`: GIL 제거 (free-threaded 모드 활성화)
- `--enable-optimizations`: PGO(Profile-Guided Optimization) 적용
- `--with-lto`: Link-Time Optimization 적용

#### 프레임워크 선택: Starlette (FastAPI 불가)

FastAPI는 pydantic-core(Rust 확장)에 의존하는데, free-threaded Python ABI(`cpython-313t`)용
pre-built wheel이 없어 설치 실패. Starlette(FastAPI의 기반)으로 직접 구현.

```python
from starlette.applications import Starlette
from concurrent.futures import ThreadPoolExecutor

thread_pool = ThreadPoolExecutor(max_workers=2)

async def cpu_mt_endpoint(request):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(thread_pool, fibonacci, 38)
    return JSONResponse({"fibonacci": result, "gil_enabled": sys._is_gil_enabled()})
```

B1에서는 `ProcessPoolExecutor`(별도 프로세스, IPC 비용)를 사용했지만,
free-threaded에서는 `ThreadPoolExecutor`(같은 프로세스, 공유 메모리)로 충분.

### 결과

#### 단일 요청 시간 비교

| 빌드 | fibonacci(38) 소요 시간 | 비율 |
|------|----------------------:|-----:|
| 표준 Python 3.12 (GIL) | ~7초 | 기준 |
| **Free-threaded 3.13 (no-GIL)** | **~14초** | **2x 느림** |

free-threaded 빌드는 단일 스레드 성능이 ~2배 느리다.
원인: biased reference counting + per-object fine-grained locking 오버헤드.

#### k6 부하 테스트 (2 VU, 60초)

| 엔드포인트 | 방식 | req/s | avg | total | 비율 |
|-----------|------|------:|----:|------:|-----:|
| `/cpu` | 이벤트 루프 블로킹 (직렬) | 0.066 | 27.5s | 5 | 기준 |
| `/cpu-mt` | ThreadPoolExecutor(2) 병렬 | **0.144** | **13.9s** | **10** | **2.16x** |

### 분석

#### 1. GIL 제거로 진짜 CPU 병렬화 달성

`/cpu-mt`에서 2 VU가 동시에 도착하면:
- GIL 있을 때: ThreadPoolExecutor라도 GIL로 순차 실행 → 한 번에 하나만
- **GIL 없을 때: 2개 스레드가 진짜 동시에 fibonacci 실행 → 2배 처리량**

avg 13.9s는 fibonacci(38)의 순수 실행 시간(대기 없음)과 일치.
이는 진짜 병렬 실행의 증거다.

#### 2. 단일 스레드 성능은 희생

free-threaded 빌드는 GIL을 제거하는 대신:
- 모든 객체에 per-object 뮤텍스를 추가
- reference counting이 atomic operation으로 변경
- 메모리 할당기가 thread-safe 버전으로 교체
- 이 오버헤드로 단일 스레드 성능이 ~2배 하락

#### 3. ProcessPoolExecutor(B1) vs ThreadPoolExecutor(free-threaded) 비교

| 항목 | ProcessPoolExecutor (B1) | ThreadPoolExecutor (free-threaded) |
|------|:-----------------------:|:---------------------------------:|
| GIL 우회 방법 | 별도 프로세스 (fork) | 같은 프로세스 (no-GIL) |
| IPC 오버헤드 | pickle 직렬화 + 파이프 | 없음 (공유 메모리) |
| 메모리 비용 | 프로세스 × 메모리 복제 | 스레드 스택만 (수 MB) |
| 향상 비율 | 1.33x | **2.16x** |
| 단일 성능 | 표준 속도 | ~2x 느림 |
| Docker fork 문제 | 있음 (hang 발생) | 없음 |
| 절대 throughput | 0.178 req/s | 0.144 req/s |

흥미로운 트레이드오프:
- **상대적 향상**: free-threaded (2.16x) > ProcessPoolExecutor (1.33x)
- **절대 throughput**: ProcessPoolExecutor (0.178) > free-threaded (0.144)
- 이유: free-threaded의 단일 스레드 성능이 2x 느려서, 2배 병렬해도 절대 속도는 비슷

### 결론

| 항목 | 판정 |
|------|------|
| GIL 없이 ThreadPoolExecutor로 CPU 병렬화 | ✅ **입증** — 2.16x 향상 |
| ProcessPoolExecutor보다 효율적 | ⚠️ **상대적으로는 맞지만 절대 성능은 비슷** |
| 프로덕션 적합성 | ❌ **아직 미성숙** — 주요 라이브러리 미호환 (pydantic 등) |

Python 3.13 free-threaded는 개념 증명(PoC) 단계다.
PEP 703의 목표인 "GIL 없는 Python"이 작동하지만:
- 단일 스레드 2x 페널티가 크고
- 대부분의 C 확장(numpy, pydantic 등)이 아직 미지원
- 프로덕션 사용은 3.14~3.15에서 생태계 안정화 후 가능할 전망

## 결정 (결론)

GIL이 없는 빌드에서는 ThreadPoolExecutor로 CPU-bound 작업이 실제로 병렬 실행됐다(2 VU에서 0.066 → 0.144 req/s, 2.16배). 다만 단일 스레드 성능이 약 2배 느려, 절대 처리량은 ProcessPoolExecutor(0.178 req/s)보다 낮았다. 원문은 주요 C 확장(pydantic-core 등)이 아직 지원하지 않아 운영에 쓰기에는 이르다고 판정했다.

## 한계

- 1회 측정, 2 VU · 60초로 요청 수가 5건 · 10건이다.
- ADR-004(로컬 직접 실행, 10 VU)와 측정 환경 · VU가 달라, 원문의 두 방식 비교 표는 같은 조건의 비교가 아니다.
- 단일 요청 시간(~7초 vs ~14초)은 측정 방법이 원문에 적혀 있지 않다.

## 후속 (원문 `future-work.md` "#1")

- CPython 3.13.13을 `--disable-gil --enable-optimizations --with-lto`로 소스 빌드
- Starlette 사용 (FastAPI는 pydantic-core 미호환으로 불가)
- **결과: ThreadPoolExecutor(2)로 CPU-bound 2.16x 향상 확인 (GIL 없이 진짜 병렬)**
- 단, 단일 스레드 성능 ~2x 하락 (biased reference counting 오버헤드)
- 상세: docs/archive/report/results-extended.md #1 섹션
