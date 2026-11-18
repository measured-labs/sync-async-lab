# 실험 결과 (Results)

> 실험일: 2026-04-05
> 환경: Docker (2 CPU, 512MB RAM), k6 from 192.168.55.158 → 192.168.55.114

---

## 원시 데이터

### I/O-bound 결과 (GET /io — sleep 200ms, 200 VU)

| Server | req/s | avg | p90 | p95 | total reqs |
|--------|------:|----:|----:|----:|-----------:|
| python-fastapi-sync | 188.5 | 798.3ms | 1009.6ms | 1011.7ms | 22,631 |
| python-fastapi-async | 735.6 | 203.7ms | 205.9ms | 207.3ms | 88,404 |
| python-django-sync | 648.4 | 231.4ms | 333.8ms | 340.0ms | 77,836 |
| python-django-async (ORM) | 260.6 | 576.8ms | 768.9ms | 812.5ms | 31,289 |
| python-django-async-raw | 269.1 | 558.1ms | 718.7ms | 750.2ms | 32,337 |
| java-spring-mvc | 739.8 | 202.6ms | 201.7ms | 202.4ms | 88,890 |
| java-spring-webflux | 741.8 | 202.1ms | 202.2ms | 202.9ms | 89,099 |
| java-spring-virtual | 717.6 | 209.0ms | 215.4ms | 221.0ms | 86,188 |
| go-server | 743.6 | 201.7ms | 202.5ms | 203.0ms | 89,275 |

### CPU-bound 결과 (GET /cpu — fibonacci(38), 100 VU)

| Server | req/s | avg | p90 | p95 | total reqs |
|--------|------:|----:|----:|----:|-----------:|
| python-fastapi-sync | 1.1 | 59999.9ms | 60000.4ms | 60000.5ms | 150 |
| python-fastapi-async | 1.0 | 58778.8ms | 60000.4ms | 60000.5ms | 153 |
| python-django-sync | 1.1 | 59999.9ms | 60000.4ms | 60000.4ms | 150 |
| python-django-async (ORM) | 1.1 | 59999.9ms | 60000.4ms | 60000.4ms | 150 |
| python-django-async-raw | 1.0 | 59130.6ms | 60000.4ms | 60000.5ms | 152 |
| java-spring-mvc | 2.5 | 30604.5ms | 58151.4ms | 60000.2ms | 328 |
| java-spring-webflux | 2.4 | 27987.3ms | 54657.4ms | 59999.7ms | 346 |
| java-spring-virtual | 2.7 | 27099.0ms | 35403.2ms | 36005.4ms | 381 |
| go-server | 2.3 | 34556.1ms | 43502.9ms | 44532.0ms | 296 |

---

## 가설 검증

### H1: FastAPI sync vs async (I/O-bound) — ✅ 가설 입증

| ���트릭 | sync | async | 배수 |
|--------|-----:|------:|-----:|
| req/s | 188.5 | 735.6 | **3.9x** |
| avg latency | 798.3ms | 203.7ms | **3.9x 빠름** |
| p95 latency | 1011.7ms | 207.3ms | **4.9x 빠름** |

**분석:**
- 가설 예상(3~5배)과 정확히 일치. async가 3.9배 높은 처리량.
- sync 서버의 p95가 1초를 넘음 → 스레드풀(~40) 포화로 큐잉 발생 확인.
- async 서버의 p95가 207ms → sleep 200ms + ��트워크 오버헤드 수준. 큐잉 거의 없음.

### H2: FastAPI sync vs async (CPU-bound) — ✅ 가설 입증

| 메트릭 | sync | async |
|--------|-----:|------:|
| req/s | 1.1 | 1.0 |
| total reqs | 150 | 153 |

**분석:**
- 두 모델 모두 ~1 req/s로 거의 동일. Python GIL + fibonacci(38)이 CPU를 완전히 점유.
- 가설대로 CPU-bound에��는 sync/async 차이 없음.
- Python의 GIL이 2코어 환경에서도 사실상 싱글 스레드로 동작하게 만듦.

### H3: Django sync vs async+ORM (I/O-bound) — ⚠️ 예상 외 결과

| 메트릭 | sync (WSGI) | async (ORM) |
|--------|------------:|------------:|
| req/s | 648.4 | 260.6 |
| avg latency | 231.4ms | 576.8ms |

**분석:**
- **가설은 "비슷하다"��으���, sync가 오히려 2.5배 빨랐다.**
- Django sync(gunicorn gthread 4 workers × 50 threads = 200 threads)가 200 VU를 효율적으로 처리.
- Django async + `sync_to_async`는 오버헤드가 생각보다 큼. 스레드풀 위임 + 코루틴 전환 비용.
- **교훈: Django에서 ORM을 쓸 ���면 async로 가는 것이 오히려 성능 악화.**

### H4: Django async-raw vs async+ORM (I/O-bound) — ❌ 가설 기각

| 메트릭 | async-raw | async (ORM) |
|--------|----------:|------------:|
| req/s | 269.1 | 260.6 |
| avg latency | 558.1ms | 576.8ms |

**분석:**
- **가설은 "raw가 훨씬 빠르다"였으나, 두 서버가 거의 동일했다.**
- Django ASGI 자체의 오버헤드가 병목��� 것으로 보임. `asyncio.sleep` 직접 사용��도 Django ASGI 미들웨어 처리 비용이 지배적.
- Django ASGI가 FastAPI 수준의 async 성능을 내지 못하는 원인은 ORM이 아니라 **ASGI 구현 자체의 오버헤드**.
- FastAPI async (735 req/s) vs Django async-raw (269 req/s) → 같은 asyncio.sleep인데 2.7배 차이.

### H5: Java MVC vs WebFlux vs Virtual Threads (I/O-bound) — ⚠️ 부분 입증

| 메트릭 | MVC | WebFlux | Virtual |
|--------|----:|--------:|--------:|
| req/s | 739.8 | 741.8 | 717.6 |
| avg | 202.6ms | 202.1ms | 209.0ms |
| p95 | 202.4ms | 202.9ms | 221.0ms |

**분석:**
- **가설 "MVC가 뒤처질 것"이 틀림.** 200 VU에서 Tomcat 스레드풀 200이 충분했기 때문.
- 세 모델 모두 ~740 req/s로 거의 동일. 200ms sleep이 병목이라 동시성 ���델 차이가 안 드러남.
- VU를 500~1000으로 올려야 MVC의 스레드풀 한계가 드러날 것 (가설에서 언급��� 대로).
- Virtual Threads가 약간 느린 건 virtual thread 스케줄링 오버헤드일 수 있음.

### H6: Java MVC vs WebFlux vs Virtual Threads (CPU-bound) — ✅ 부분 입증

| 메트릭 | MVC | WebFlux | Virtual |
|--------|----:|--------:|--------:|
| req/s | 2.5 | 2.4 | 2.7 |
| total | 328 | 346 | 381 |

**분석:**
- 세 모델 모두 2~3 req/s로 비슷 (2코어 병목).
- Virtual Threads가 약간 우세 (381 reqs). 스레드 관리 오버헤드가 적어서일 수 있음.
- Java가 Python보다 CPU-bound��서 2배 이상 빠름 (GIL 없이 2코어 활용).

### H7: Go (I/O-bound & CPU-bound) — ✅ 가설 입증

| 메트릭 | Go (IO) | Go (CPU) |
|--------|--------:|---------:|
| req/s | 743.6 | 2.3 |
| p95 | 203.0ms | 44532.0ms |

**분석:**
- I/O: 743.6 req/s로 최상위권 (Java WebFlux/MVC와 동등).
- CPU: 2.3 req/s로 Java와 비슷한 ��위.
- 가설대로 Go는 I/O-bound에서 최상위, CPU-bound에서 Java급.

### H8: Go sync/async 무의미성 — ✅ 입증

- Go 서버 1개의 I/O 결과가 ��른 async 서버들(FastAPI async, WebFlux)과 동등 → goroutine이 blocking 스타일 코드를 비동기로 처리함 확인.

---

## 핵심 발견

### I/O-bound 처��량 순위

| 순위 | 서버 | req/s |
|------|------|------:|
| 1 | go-server | 743.6 |
| 2 | java-spring-webflux | 741.8 |
| 3 | java-spring-mvc | 739.8 |
| 4 | python-fastapi-async | 735.6 |
| 5 | java-spring-virtual | 717.6 |
| 6 | python-django-sync | 648.4 |
| 7 | python-django-async-raw | 269.1 |
| 8 | python-django-async (ORM) | 260.6 |
| 9 | python-fastapi-sync | 188.5 |

### 예상 외 발견

1. **Django sync > Django async**: WSGI + gthread가 ASGI보다 빠름. Django에서 async는 오히려 성능 저하.
2. **Django ASGI 자체가 병목**: ORM이 아니라 Django ASGI 미들웨어 처리 비용이 지배적.
3. **Java MVC = WebFlux = Virtual Threads (200 VU에서)**: 스레드풀 200이 충분하면 ��델 차이 없음.
4. **Python CPU-bound는 GIL에 의해 사실상 싱글코어**: 2코어 환경에서도 ~1 req/s.
5. **Java/Go는 CPU-bound에서 Python의 2배 이상**: GIL 없이 멀티코어 활용.

---

## 추가 실험 제안

1. **VU 500/1000으로 올려서 Java MVC 스레드풀 한계 확인**
2. **Python CPU-bound에서 ProcessPoolExecutor 사용 시 성능 변화**
3. **Django ASGI 오버헤드 원인 추가 프로파일링**
4. **Java Virtual Threads에서 VU 5000 이상 극한 테스트**
