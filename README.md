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

## 엔드포인트

| 엔드포인트 | 역할 |
|-----------|------|
| GET /io | I/O-bound (sleep 200ms) |
| GET /cpu | CPU-bound (fibonacci) |

## 실행

```bash
# 서버 전체 기동 (Docker)
docker compose up -d

# k6 테스트 (별도 PC에서)
cd k6
./run-all.sh
```

## 실험 환경

- Docker 리소스 제한: 2 CPU, 512MB RAM (전 서버 동일)
- k6: 별도 PC에서 192.168.55.114 대상으로 실행
- 측정: 1개 서버씩 순차적으로 요청

## 폴더 구조

```
servers/          # 9개 서버 소스
k6/               # k6 테스트 시나리오
report/           # 가설 + 실험 결과 (git 추적)
docs/             # 설계 문서 (git 미추적)
```
