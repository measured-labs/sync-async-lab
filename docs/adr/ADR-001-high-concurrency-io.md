# ADR-001: 고부하 I/O — VU 500 → 1000에서 동시성 모델 차이 (A1)

- 상태: 끝남 — 2026-04-05 측정 · 결과 커밋 225438a
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "A1", [results-extended.md](../archive/report/results-extended.md) "A1" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 줄임 이름: A1은 확장 실험 목록(A = 기존 서버로 바로 하는 확장, B = 새 서버 · 설정이 필요한 실험, C = 운영 관점)의 첫 항목이다.
- 선행: [ADR-000](ADR-000-baseline-io-cpu.md) — 200 VU에서는 MVC · WebFlux · 가상 스레드 차이가 드러나지 않았다.

## 질문

Tomcat 스레드풀(200)을 넘는 동시 요청이 오면 Spring MVC는 얼마나 느려지고, WebFlux · 가상 스레드 · Go · FastAPI async는 버티는가.

## 선택지

ADR-000의 서버 중 python-django-async(ORM)를 뺀 8개: python-fastapi-sync, python-fastapi-async, python-django-sync, python-django-async-raw, java-spring-mvc, java-spring-webflux, java-spring-virtual, go-server.

## 실험 설계

- 엔드포인트: `GET /io`(sleep 200ms).
- k6 시나리오 `k6/scenarios/high-concurrency-io.js`: 30초 동안 500 VU까지 올림 → 500 VU 60초 → 30초 동안 1000 VU까지 → 1000 VU 60초 → 30초 동안 0까지. 표의 req/s · 응답 시간은 이 3분 30초 전체의 값이다(1000 VU 구간만 따로 잰 값이 아니다).
- 환경: Docker 2 CPU · 512MB RAM, k6는 별도 PC(ADR-000과 같음). 실행 스크립트 `k6/run-high-concurrency.sh`.

### 가설 (원문)

#### 가설
**VU 500 이상에서 Java MVC의 성능이 급격히 하락하고, WebFlux/Virtual Threads/Go는 안정적일 것이다.**

#### 근거
- 1차 실험: 200 VU에서 MVC(740 req/s) = WebFlux(741) = Virtual(717). Tomcat 200 스레드가 충분했음.
- VU 500: 스레드풀 200 초과 → 300개 요청이 큐잉 → latency 급증 예상
- VU 1000: MVC는 심각한 큐잉, WebFlux/Virtual/Go는 여전히 안정적일 것

#### 예상 결과
- MVC: VU 500에서 p95 > 1s, VU 1000에서 p95 > 2s
- WebFlux/Virtual/Go: VU 1000에서도 p95 ≈ 200-300ms
- FastAPI async: VU 1000에서도 안정적 (이벤트 루프)
- FastAPI sync: VU 500에서 이미 심각한 큐잉 (스레드풀 ~40)

## 결과 (원문)

> 실험일: 2026-04-05 · 환경: Docker (2 CPU, 512MB RAM), k6 서버(별도 PC) → 앱 서버(Docker 호스트)

#### 결과

| Server | req/s | avg | p90 | p95 | total |
|--------|------:|----:|----:|----:|------:|
| python-fastapi-sync | 195.9 | 3314.4ms | 5050.8ms | 5054.4ms | 41,160 |
| python-fastapi-async | 1558.1 | 412.5ms | 568.9ms | 602.8ms | 327,460 |
| python-django-sync | 942.9 | 682.6ms | 1177.9ms | 1327.5ms | 198,134 |
| python-django-async-raw | 281.9 | 2296.0ms | 3917.5ms | 4061.5ms | 59,230 |
| java-spring-mvc | 953.5 | 674.5ms | 1003.4ms | 1004.3ms | 200,469 |
| java-spring-webflux | 3160.9 | 203.1ms | 203.9ms | 212.3ms | 664,337 |
| java-spring-virtual | 2333.0 | 275.4ms | 447.9ms | 483.1ms | 490,256 |
| go-server | 3179.5 | 202.0ms | 202.8ms | 204.0ms | 668,099 |

#### 가설 검증: ✅ 입증

- **Java MVC**: 200 스레드풀이 500/1000 VU에서 포화됨. p95 = 1004ms (큐잉 확인).
- **WebFlux**: 3161 req/s — 500→1000 VU 단계 시나리오 전체에서 p95 = 212ms로 안정적.
- **Virtual Threads**: 2333 req/s — WebFlux보다 약간 낮지만 MVC보다 2.4배 빠름.
- **Go**: 3180 req/s — WebFlux와 동급 최상위.
- **FastAPI async**: 1558 req/s — Python에서 최고. 하지만 Go/WebFlux의 절반 수준.
- **FastAPI sync**: 196 req/s — 스레드풀 ~40이 완전히 포화.

> 2026-11-18 주석: 원문의 "VU 1000에서도 p95 = 212ms"를 위처럼 바꿨다. 이 시나리오는 VU를 500에서 1000으로 올리는 단계형이고, p95와 req/s는 3분 30초 전체에서 집계한 값이다. 1000 VU 구간만의 응답 시간은 따로 없다.

#### I/O-bound 최종 순위 (500→1000 VU 단계 시나리오 전체)

| 순위 | 서버 | req/s | 동시성 모델 |
|------|------|------:|------------|
| 1 | Go | 3179.5 | goroutine |
| 2 | Spring WebFlux | 3160.9 | Reactor 이벤트 루프 |
| 3 | Spring Virtual Threads | 2333.0 | M:N 가상 스레드 |
| 4 | FastAPI async | 1558.1 | asyncio 이벤트 루프 |
| 5 | Spring MVC | 953.5 | OS 스레드 200 (포화) |
| 6 | Django sync | 942.9 | gthread 200 (포화) |
| 7 | Django async-raw | 281.9 | ASGI 오버헤드 |
| 8 | FastAPI sync | 195.9 | 스레드풀 ~40 (극심한 포화) |

> 2026-11-18 주석: 원문 표 제목은 "I/O-bound 최종 순위 (1000 VU)"였다. 값은 500→1000 VU 단계 시나리오 전체의 평균이다. 1000 VU 유지 구간만의 추정치는 아래 한계 절의 구간별 표에 있다.


2026-11-18 확인: k6 원본 로그 `k6/results/high-concurrency-20260405-074723/*.log`(667~668행)에서 8개 서버 모두 `http_req_failed` 0.00%이고, req/s가 위 표와 같다.

## 결정 (결론)

VU 500~1000에서 동시성 모델 차이가 드러났다. Go(3,179.5 req/s)와 WebFlux(3,160.9)가 가장 높았고, 가상 스레드(2,333.0)는 MVC(953.5)의 2.4배였다. 요청 스레드 200개를 쓰는 MVC(Tomcat 기본 200)와 Django sync(gunicorn 4 프로세스 × 50 스레드)는 약 1,000 req/s(스레드 200 ÷ 0.2초인 이론 상한) 근처에 머물렀다. 전체 평균이 953.5 · 942.9로 그보다 낮은 것은 VU를 올리고 내리는 구간이 평균에 섞였기 때문이다(아래 구간별 추정). 가설(MVC는 VU 500 이상에서 급락, WebFlux · 가상 스레드 · Go는 안정)은 입증으로 판정했다.

## 한계

- 1회 측정. 호스트 하드웨어 · k6 버전 기록 없음.
- 원문은 500 VU 구간과 1000 VU 구간을 나눠 집계하지 않았다. 2026-11-18에 k6 원본 로그의 진행 줄로 구간별 처리량을 추정했다(아래 표). 응답 시간(p95)은 구간별로 나눌 수 없어, 가설의 "VU 500에서 p95 > 1s, VU 1000에서 p95 > 2s"는 여전히 그대로 비교할 수 없다.

### 구간별 처리량 추정 (2026-11-18 계산)

- 근거: `k6/results/high-concurrency-20260405-074723/<서버>.log`의 1초마다 찍힌 진행 줄 `running (XmYY.Ys), N/1000 VUs, C complete and 0 interrupted iterations`.
- 계산: 500 VU 유지 구간 = (90초 시점 C − 30초 시점 C) ÷ 60, 1000 VU 유지 구간 = (180초 시점 C − 120초 시점 C) ÷ 60. C는 끝난 요청(iteration) 수이고, 이 시나리오에서 iteration 하나 = `/io` 요청 하나다. 진행 줄은 1초 단위라 경계에서 몇 건씩 차이가 날 수 있다.

| 서버 | 500 VU 유지 (req/s) | 1000 VU 유지 (req/s) | 전체 평균 (원문) |
|---|---:|---:|---:|
| Go | 2,477 | 4,938 | 3,179.5 |
| Spring WebFlux | 2,476 | 4,886 | 3,160.9 |
| Spring 가상 스레드 | 2,340 | 2,986 | 2,333.0 |
| FastAPI async | 1,534 | 1,864 | 1,558.1 |
| Spring MVC | 997 | 997 | 953.5 |
| Django sync (WSGI) | 993 | 990 | 942.9 |
| Django async-raw | 318 | 254 | 281.9 |
| FastAPI sync | 198 | 198 | 195.9 |

- 이론 상한과 비교: 200ms 대기만 있다면 500 VU는 2,500 req/s, 1000 VU는 5,000 req/s가 상한이다. Go · WebFlux는 두 구간 모두 상한의 약 98~99%, MVC · Django sync는 스레드 200개의 상한 1,000 req/s 근처에 머물렀다. 가상 스레드는 1000 VU에서 상한의 약 60%였다.
- 가상 스레드가 WebFlux보다 낮은 이유(2,333 vs 3,161)는 따로 조사하지 않았다.
