# ADR-011: 부하 중 graceful shutdown (C1)

- 상태: 끝남(결과 재확인 필요 — 아래 한계) — 2026-04-05 측정 · 결과 커밋 225438a
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "C1", [results-extended.md](../archive/report/results-extended.md) "C1" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기는 없다. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 줄임 이름: C1은 확장 실험 목록 C(운영 관점)의 첫 항목이다.

## 질문

부하를 받는 중에 컨테이너를 멈추면(`docker stop`), 이벤트 루프 모델이 스레드 모델보다 진행 중 요청을 덜 잃는가.

## 선택지

python-fastapi-sync, python-fastapi-async, java-spring-mvc, java-spring-virtual, go-server, node-server(`k6/run-shutdown-test.sh`의 서버 목록).

## 실험 설계

- k6 시나리오 `k6/scenarios/shutdown-test.js`: 10초 동안 100 VU까지 → 100 VU 50초, `GET /io`(요청 타임아웃 5초).
- `k6/run-shutdown-test.sh`: k6를 띄우고 20초 뒤 ssh로 Docker 호스트에 `docker stop --time=10 <컨테이너>`를 보낸다. k6가 끝나면 `docker start`로 다시 띄운다.

### 가설 (원문)

#### 가설
**이벤트 루프 모델이 스레드 모델보다 graceful shutdown이 깨끗할 것이다 (진행 중 요청 드롭률이 낮음).**

#### 근거
- 이벤트 루프: 진행 중 작업 완료 후 종료가 자연스러움
- 스레드 모델: 200 스레드가 각각 작업 중 → 전부 완료 대기 or 강제 종료

## 결과 (원문)

### 결과

| Server | req/s | total | fail% | p95 |
|--------|------:|------:|------:|----:|
| python-fastapi-sync | 191.2 | 11,562 | 0.0% | 547.1ms |
| python-fastapi-async | 448.5 | 26,998 | 0.0% | 205.7ms |
| java-spring-mvc | 450.1 | 27,062 | 0.0% | 202.9ms |
| java-spring-virtual | 449.4 | 27,034 | 0.0% | 204.1ms |
| go-server | 451.9 | 27,200 | 0.0% | 203.6ms |
| node-server | 452.7 | 27,250 | 0.0% | 204.1ms |

### 가설 검증: ❌ 기각

- **모든 서버가 0% 요청 드롭**
- Docker의 `--time=10` (SIGTERM 후 10초 유예)이 충분하여 진행 중 요청 모두 완료
- 동시성 모델과 무관하게 모든 프레임워크가 SIGTERM을 올바르게 처리
- **graceful shutdown은 동시성 모델이 아닌 프레임워크 구현 품질에 의존**

## 결정 (결론)

원문은 6개 서버 모두 요청 실패 0%로, 가설(이벤트 루프 모델이 더 깨끗하게 종료)을 기각하고 "graceful shutdown은 동시성 모델이 아니라 프레임워크 구현에 달려 있다"고 판정했다.

## 한계

- 2026-11-18 문서 정리 중 확인: k6 원본 로그 `k6/results/shutdown-20260405-094804/go-server.log`의 진행 줄을 보면, 완료 요청 수가 19초 6,900건 → 25초 9,850건 → 55초 24,600건으로 `docker stop`을 보낸 20초 뒤에도 초당 약 500건씩 꾸준히 늘었다. python-fastapi-sync(스레드풀 포화로 191 req/s)를 뺀 5개 서버도 total이 약 27,000건(60초 × 약 450 req/s)으로, 60초 내내 요청을 처리한 값과 같다. 컨테이너가 실제로 멈췄다는 기록(ssh · docker 출력)은 결과 폴더에 없다. 따라서 이 결과는 "종료 중 요청을 잃지 않았다"가 아니라 "종료가 일어났는지 확인되지 않았다"로 읽어야 한다. 원문 판정은 고치지 않았다.
- 1회 측정. Django 서버와 WebFlux는 목록에 없다.
