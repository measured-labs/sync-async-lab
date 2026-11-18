# ADR-009: 서버별 메모리 사용량 (B4)

- 상태: 끝남(대략치만) — 2026-04-05 측정 · 결과 커밋 225438a
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "B4", [results-extended.md](../archive/report/results-extended.md) "B4" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기는 없다. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 줄임 이름: B4는 확장 실험 목록 B의 넷째 항목이다.

## 질문

같은 리소스 제한(2 CPU · 512MB)에서 Python · Java · Go · Node.js 서버의 메모리 사용량은 어떻게 다른가.

## 선택지

Docker에 띄운 모든 서버 컨테이너. `k6/collect-stats.sh`로 `docker stats`를 모았다.

## 가설 (원문)

### 가설
**Go와 이벤트 루프 모델이 스레드 모델보다 메모리 효율이 높을 것이다. Java는 JVM 오버헤드로 가장 높을 것이다.**

### 근거
- goroutine: 2-8KB per connection
- OS thread: ~1MB stack per thread
- JVM: 기본 힙 + 메타스페이스 + 스레드 스택

## 결과 (원문)

> docker stats 수집 (Node.js I/O 테스트 중)

서버별 idle 메모리는 docker stats에서 확인된 대략적 수준:
- Python (FastAPI/Django): ~50-80MB
- Java (Spring): ~200-350MB (JVM 힙)
- Go: ~10-20MB
- Node.js: ~40-60MB

**Java가 가장 높은 메모리 사용, Go가 가장 낮음.**

## 결정 (결론)

원문은 Java(JVM 힙)가 가장 많이, Go가 가장 적게 쓴다고 판정했다.

## 한계

- 결과가 범위로 적힌 대략치다("docker stats에서 확인된 대략적 수준"). 서버별 정확한 값 · 측정 시점이 원문에 없다.
- 로컬 작업 트리에만 있는 `results/memory-20260405-184059/docker-stats.csv`(2026-04-05 18:40:59 ~ 18:45:24, 컨테이너마다 36회)가 원문의 근거인지는 알 수 없다. 원문에 이 파일이 언급되지 않는다. 이 파일의 컨테이너별 메모리(최소~최대, MiB)는 원문 범위와 다른 곳이 있다(2026-11-18 계산):

| 원문 분류 | 원문 범위 | csv 값 (MiB) |
|---|---|---|
| Go | ~10-20MB | go-server 7.2~7.8 |
| Node.js | ~40-60MB | node-server 15.1~33.9 |
| Python (FastAPI/Django) | ~50-80MB | fastapi-sync 48.5, fastapi-async 58.9~59.2, django-async 35.7, django-async-raw 57.4, django-sync 160.0 |
| Java (Spring) | ~200-350MB | mvc 265.0~265.3, webflux 260.1~260.3, virtual 249.1 |

  csv에는 이 랩과 무관한 컨테이너 1개와 postgres(137.2~139.6)도 들어 있다. Go · Node.js · Django sync · Django async는 원문 범위 밖이다. 원문 수치는 고치지 않았다. 이 csv는 저장소에 올리지 않는 로컬 파일이다(다른 프로젝트의 컨테이너 이름이 섞여 있어 커밋에서 뺐다). 그래서 공개 저장소의 독자는 위 비교표를 다시 확인할 수 없다.
- 부하 중 메모리는 Node.js I/O 테스트 중 한 번 모은 것이다. 서버마다 자기 부하를 받을 때의 메모리는 아니다. WebSocket 1000 연결 중 메모리는 [ADR-008](ADR-008-websocket.md)에 있다.
