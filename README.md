# sync-async-lab

동기/비동기 처리 방식의 성능 차이를 실험적으로 검증하는 프로젝트.

## 실험 대상 서버

| # | 서버 | 프레임워크 | 동시성 모델 | 포트 |
|---|------|-----------|------------|------|
| 1 | python-fastapi-sync | FastAPI + def | 스레드풀 | 8001 |
| 2 | python-fastapi-async | FastAPI + async def | asyncio 이벤트 루프 | 8002 |
| 3 | python-django-sync | Django WSGI (gunicorn) | 프로세스/스레드 | 8003 |
| 4 | python-django-async | Django ASGI (uvicorn) + ORM | asyncio + sync_to_async | 8004 |
| 5 | python-django-async-raw | Django ASGI + raw SQL | 순수 async I/O | 8005 |
| 6 | java-spring-mvc | Spring MVC (Tomcat) | OS 스레드 1:1 | 8006 |
| 7 | java-spring-webflux | Spring WebFlux (Netty) | Reactor 이벤트 루프 | 8007 |
| 8 | java-spring-virtual | Spring MVC + Virtual Threads | M:N 가상 스레드 | 8008 |
| 9 | go-server | Go net/http | goroutine (M:N) | 8009 |
| 10 | node-server | Node.js Express | 싱글 스레드 이벤트 루프 | 8010 |

## 엔드포인트

| 엔드포인트 | 역할 |
|-----------|------|
| GET /io | I/O-bound (sleep 200ms) |
| GET /cpu | CPU-bound (fibonacci 38) |
| GET /db | DB I/O (PostgreSQL pg_sleep 200ms) |

## 핵심 결과

### I/O-bound 처리량 (1000 VU)

| 순위 | 서버 | req/s |
|------|------|------:|
| 1 | Go | 3,180 |
| 2 | Spring WebFlux | 3,161 |
| 3 | Spring Virtual Threads | 2,333 |
| 4 | FastAPI async | 1,558 |
| 5 | Spring MVC | 954 |
| 6 | Django sync (WSGI) | 943 |
| 7 | Django async-raw | 282 |
| 8 | FastAPI sync | 196 |

### 주요 발견

- **Django async가 sync보다 느리다**: WSGI+gthread가 ASGI보다 2.5배 빠름
- **고부하에서 동시성 모델 차이가 극명**: 200 VU에서 비슷하던 서버들이 1000 VU에서 3배 이상 차이
- **DB I/O에서는 커넥션 풀 크기가 왕**: 동시성 모델보다 풀 크기가 처리량 상한 결정
- **Go는 blocking 코드로 최상위 성능**: sync/async 구분 없이 goroutine이 자동 비동기
- **Graceful Shutdown은 모델과 무관**: 모든 프레임워크가 0% 요청 드롭

## 실행

```bash
# 서버 전체 기동 (Docker, PostgreSQL 포함)
docker compose up -d

# k6 테스트 (별도 PC에서)
cd k6
./run-all.sh                  # 기본 I/O + CPU 테스트
./run-high-concurrency.sh     # 500/1000 VU 고부하
./run-db-bound.sh             # PostgreSQL DB I/O
```

## 실험 환경

- Docker 리소스 제한: 2 CPU, 512MB RAM (전 서버 동일)
- PostgreSQL 16 (Docker, 동일 리소스 제한)
- k6: 별도 PC에서 192.168.55.114 대상으로 실행
- 측정: 1개 서버씩 순차적으로 요청 (컨텍스트 스위칭 방지)

## 폴더 구조

```
servers/          # 10개 서버 소스
k6/               # k6 테스트 시나리오 + 실행 스크립트
report/           # 가설 + 실험 결과 (git 추적)
  hypotheses.md         # 1차 가설 (H1-H8)
  hypotheses-extended.md # 확장 가설 (A1-C1)
  results.md            # 1차 결과
  results-extended.md   # 확장 결과
  future-work.md        # 미완료 실험 + 향후 작업
docs/             # 설계 문서 (git 미추적)
```

## 상세 결과

- [1차 실험 결과](report/results.md)
- [확장 실험 결과](report/results-extended.md)
- [미완료 실험 및 향후 작업](report/future-work.md)
