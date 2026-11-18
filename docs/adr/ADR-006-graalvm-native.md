# ADR-006: Spring MVC를 GraalVM Native Image로 — 시작 시간 · 메모리 · 처리량 (B2)

- 상태: 끝남 — 2026-04-11 측정 · 결과 커밋 342ecff
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "B2", [results-extended.md](../archive/report/results-extended.md) "B2", [future-work.md](../archive/report/future-work.md) "B2"(측정 전 계획) — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: "sleep 200ms가 지배적이라" → "sleep 200ms가 응답 시간의 대부분을 차지해"; 표 머리 "승자" → "앞선 쪽"; 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 원문 판정(원문 절 제목): "B2: Java GraalVM Native Image — ⚠️ 부분 입증 (스타트업/메모리 극적 개선, 처리량은 JIT에 열세)". 같은 원문의 결론 표는 세 항목 모두 "✅ 입증"이다.
- 줄임 이름: B2는 확장 실험 목록 B의 둘째 항목이다.

## 질문

같은 Spring MVC 코드를 JVM(JIT) 대신 GraalVM Native Image(AOT)로 빌드하면 콜드 스타트 · 메모리 · 처리량이 어떻게 달라지는가.

## 선택지

| 버전 | 서버 | 포트 |
|---|---|---|
| JVM (Temurin 21, JIT) | java-spring-mvc | 8006 |
| Native (GraalVM CE 21, AOT) | java-spring-mvc-native | 8011 |

Java 코드는 같고 빌드 설정 · Dockerfile만 다르다.

## 가설 (원문)

### 가설
**GraalVM native은 JVM 대비 콜드 스타트가 빠르고 메모리가 적지만, 처리량은 비슷하거나 약간 낮을 것이다.**

### 근거
- GraalVM native: AOT 컴파일 → 즉시 시작, 낮은 메모리
- JIT 최적화 없음 → 장기 실행 시 throughput이 JVM보다 낮을 수 있음

측정 전 계획(원문 `future-work.md`, 2026-04-05 — 빌드 시간 때문에 그때는 미진행):

**상태:** 빌드 시간 (10분+)으로 미진행

**구현 계획:**
```dockerfile
FROM ghcr.io/graalvm/native-image-community:21 AS build
WORKDIR /app
COPY . .
RUN gradle nativeCompile --no-daemon

FROM gcr.io/distroless/base
COPY --from=build /app/build/native/nativeCompile/spring-mvc-native .
CMD ["./spring-mvc-native"]
```

**build.gradle.kts 변경:**
```kotlin
plugins {
    id("org.graalvm.buildtools.native") version "0.10.4"
}
```

**테스트 항목:**
- 콜드 스타트 시간 (JVM ~3s vs Native ~0.1s 예상)
- 메모리 사용량 (JVM ~300MB vs Native ~50MB 예상)
- Throughput 비교 (JIT 최적화 없어서 JVM보다 낮을 수 있음)
- `/io`, `/cpu`, `/db` 전부 테스트

## 실험 설계 · 결과 (원문)

> 실험일: 2026-04-11
> 환경: Docker (2 CPU, 512MB RAM), k6 서버(별도 PC) → 앱 서버(Docker 호스트)
> GraalVM CE 21 (native-image-community), Spring Boot 3.4.4

### 실험 개요

기존 `java-spring-mvc`(JVM + JIT)를 GraalVM Native Image로 AOT 컴파일하여 동일 조건에서 비교한다.
Java 코드(`BenchmarkController.java`, `Application.java`)는 **한 줄도 변경하지 않았다.**
변경은 빌드 설정과 Dockerfile뿐이다.

### 수행한 작업

#### 1. 서버 디렉토리 생성

`servers/java-spring-mvc`를 `servers/java-spring-mvc-native`로 복사한 뒤, 빌드 설정만 변경했다.

**변경 파일 1: `build.gradle.kts`** — GraalVM native 플러그인 추가

```kotlin
plugins {
    java
    id("org.springframework.boot") version "3.4.4"
    id("io.spring.dependency-management") version "1.1.7"
    id("org.graalvm.buildtools.native") version "0.10.4"  // ← 추가
}
```

이 플러그인이 하는 일:
- `nativeCompile` Gradle task를 등록한다
- Spring AOT(Ahead-of-Time) 프로세서를 실행하여 리플렉션 힌트, 프록시 설정, 직렬화 메타데이터를 자동 생성한다
- `native-image` 도구를 호출하여 GraalVM Substrate VM 기반의 독립 실행 바이너리를 생성한다

**변경 파일 2: `settings.gradle.kts`** — 프로젝트명 변경

```kotlin
rootProject.name = "spring-mvc-native"
```

이 이름이 네이티브 바이너리 파일명(`spring-mvc-native`)이 된다.

**변경 파일 3: `Dockerfile`** — GraalVM 빌드 → 경량 실행 이미지

```dockerfile
# 1단계: GraalVM 빌드 이미지에서 네이티브 컴파일
FROM container-registry.oracle.com/graalvm/native-image-community:21 AS build
RUN microdnf install -y findutils unzip && microdnf clean all
WORKDIR /app
COPY build.gradle.kts settings.gradle.kts ./
COPY gradle ./gradle
COPY src ./src
RUN curl -sL https://services.gradle.org/distributions/gradle-8.12-bin.zip -o gradle.zip \
    && unzip -q gradle.zip \
    && rm gradle.zip
RUN ./gradle-8.12/bin/gradle nativeCompile --no-daemon

# 2단계: 경량 실행 이미지 (JVM 불필요)
FROM debian:bookworm-slim
WORKDIR /app
COPY --from=build /app/build/native/nativeCompile/spring-mvc-native .
EXPOSE 8080
CMD ["./spring-mvc-native"]
```

JVM Dockerfile과의 핵심 차이:

| 항목 | JVM | Native |
|------|-----|--------|
| 빌드 이미지 | `gradle:8.12-jdk21` | `graalvm/native-image-community:21` |
| 빌드 명령 | `gradle bootJar` → JAR 생성 | `gradle nativeCompile` → 바이너리 생성 |
| 실행 이미지 | `eclipse-temurin:21-jre` (JRE 필요) | `debian:bookworm-slim` (JRE 불필요) |
| 실행 명령 | `java -jar app.jar` | `./spring-mvc-native` |
| 빌드 시간 | ~30초 | **~3분 23초** (네이티브 컴파일 2분 11초) |
| 빌드 메모리 | ~1GB | **~4.78GB** (Peak RSS) |

#### 2. docker-compose.yml에 추가

```yaml
java-spring-mvc-native:
  build: ./servers/java-spring-mvc-native
  ports:
    - "8011:8080"
  environment:
    - DB_HOST=postgres
  depends_on:
    postgres:
      condition: service_healthy
  cpus: 2.0
  mem_limit: 512m
  restart: unless-stopped
```

기존 서버들과 동일한 리소스 제약(2 CPU, 512MB)을 적용했다. 포트는 8011.

#### 3. 빌드 과정에서의 문제 해결

1. **ghcr.io 403 Forbidden**: `ghcr.io/graalvm/native-image-community:21` 이미지 pull 실패
   → Oracle 레지스트리(`container-registry.oracle.com`)로 변경하여 해결

2. **unzip 미설치**: GraalVM 이미지에 `unzip`이 없어서 Gradle zip 압축 해제 실패
   → `microdnf install -y findutils unzip` 으로 해결

3. **findutils 미설치**: Gradle 빌드 시 `xargs` 등 유틸리티 필요
   → 위와 동일하게 `microdnf`으로 해결

### 콜드 스타트 비교

서버를 완전히 중지한 상태에서 `docker compose up -d`로 시작 → 첫 HTTP 요청이 성공할 때까지의 시간.

| 버전 | 콜드 스타트 | 비율 |
|------|----------:|-----:|
| JVM (Temurin 21, -Xmx256m) | 6,520 ms | 기준 |
| **Native (GraalVM CE 21)** | **346 ms** | **18.8x 빠름** |

JVM은 클래스 로딩 → 바이트코드 검증 → JIT 워밍업 단계를 거친다.
Native는 이 과정이 모두 AOT 컴파일 시점에 완료되어 있어 프로세스 시작 즉시 요청 처리 가능.

### 메모리 사용량 비교 (Idle)

서버 시작 후 부하 없는 상태에서 `docker stats`로 측정.

| 버전 | Idle 메모리 | 비율 |
|------|----------:|-----:|
| JVM | 212 MB | 기준 |
| **Native** | **37 MB** | **5.7x 절약** |

JVM은 `-Xms256m`으로 힙을 미리 확보하므로 기본 메모리가 높다.
Native는 필요한 만큼만 할당하므로 idle 상태에서 극적으로 낮다.

### 처리량(Throughput) 비교

동일 조건(Docker 2 CPU, 512MB, k6는 별도 PC)에서 **동일 날짜에** JVM과 Native를 번갈아 테스트.

#### I/O-bound (GET /io — sleep 200ms, 200 VU)

| 버전 | req/s | avg | p90 | p95 | total | fail% |
|------|------:|----:|----:|----:|------:|------:|
| JVM (1차 실험) | 739.8 | 202.6ms | 202.0ms | 202.4ms | 88,776 | 0% |
| **Native** | **740.8** | **202.5ms** | **202.8ms** | **204.7ms** | **88,926** | **0%** |

**I/O-bound에서는 차이 없음.** sleep 200ms가 응답 시간의 대부분을 차지해 JIT/AOT 차이가 드러나지 않음.

#### CPU-bound (GET /cpu — fibonacci(38), 100 VU) — 동일 날짜 비교

| 버전 | req/s | avg | p95 | total | fail% |
|------|------:|----:|----:|------:|------:|
| **JVM (재측정)** | **2.61** | **31.07s** | **49.09s** | **327** | **0.3%** |
| **Native** | **2.09** | **36.26s** | **1m0s** | **280** | **17.5%** |

**CPU-bound에서 Native가 ~20% 느림.** JVM의 JIT 컴파일러(C2)가 fibonacci 재귀를
런타임에 최적화하는 반면, Native는 AOT 컴파일 시점의 최적화만 적용되기 때문이다.

구체적으로:
- **JIT(C2 컴파일러)**: 런타임에 핫스팟을 감지하고 어그레시브 인라이닝, 루프 언롤링, 
  이스케이프 분석, 레지스터 할당 최적화를 수행한다. fibonacci 같은 재귀 함수는 
  JIT가 반복적으로 호출 패턴을 분석하여 점점 더 최적화된 네이티브 코드를 생성한다.
- **AOT(GraalVM)**: 컴파일 시점에 가능한 최적화만 적용한다. 런타임 프로파일링 정보가 
  없으므로 JIT처럼 어그레시브한 최적화가 불가능하다. 특히 재귀 함수의 인라이닝 깊이 결정, 
  분기 예측 힌트 등에서 JIT보다 보수적이다.

Native의 17.5% fail은 k6 기본 timeout(60s)에 걸린 것이다.
JVM이 더 빠르게 처리하여 큐에 쌓인 요청이 timeout 안에 소화되었지만,
Native는 요청당 처리 시간이 더 길어 일부가 timeout에 걸렸다.

### 전체 비교 요약

| 항목 | JVM | Native | 앞선 쪽 |
|------|----:|-------:|:----:|
| 콜드 스타트 | 6,520ms | 346ms | **Native (18.8x)** |
| Idle 메모리 | 212MB | 37MB | **Native (5.7x)** |
| I/O 처리량 | 739.8 req/s | 740.8 req/s | 동률 |
| CPU 처리량 | 2.61 req/s | 2.09 req/s | **JVM (1.25x)** |
| Docker 이미지 빌드 | ~30초 | ~3분 23초 | JVM |
| 빌드 메모리 | ~1GB | ~4.78GB | JVM |

### 결론

| 항목 | 판정 |
|------|------|
| 콜드 스타트가 빠르다 | ✅ **입증** — 18.8배 빠름 |
| 메모리가 적다 | ✅ **입증** — 5.7배 절약 |
| 처리량은 비슷하거나 약간 낮다 | ✅ **입증** — I/O 동일, CPU 20% 낮음 |

GraalVM Native Image는 **서버리스/FaaS, 마이크로서비스 스케일아웃, 컨테이너 밀도 최적화** 등
빠른 스타트업과 낮은 메모리가 중요한 환경에 적합하다.
반면 **CPU 집약적이고 long-running 서버**에서는 JIT의 런타임 최적화가 더 유리하다.

## 결정 (결론)

Native Image는 콜드 스타트(6,520ms → 346ms, 18.8배)와 idle 메모리(212MB → 37MB, 5.7배)에서 크게 앞섰고, I/O-bound 처리량은 같았다(739.8 vs 740.8 req/s). CPU-bound 처리량은 JVM이 약 20% 높았다(2.61 vs 2.09 req/s). 원문은 빠른 시작 · 적은 메모리가 중요한 곳(서버리스, 스케일아웃)에는 Native, CPU를 오래 쓰는 서버에는 JVM이 맞다고 판정했다.

## 한계

- 각 1회 측정. 콜드 스타트 · idle 메모리는 1회 값이다.
- I/O-bound의 JVM 값(739.8 req/s)은 2026-04-05 1차 실험 값이고, CPU-bound만 같은 날 다시 쟀다. 원문 표의 JVM 행은 total 88,776 · p90 202.0ms로, 1차 결과([ADR-000](ADR-000-baseline-io-cpu.md))의 88,890 · 201.7ms와 다르다(req/s · avg · p95는 같다).
- CPU-bound Native는 17.5%가 k6 타임아웃(60초)으로 실패했다. req/s는 실패를 포함한 값이다. 2026-11-18 계산: 성공 건만 세면 Native가 JVM보다 약 29~34% 낮다. total × (1 − fail%)로는 JVM 327 × 0.997 ≈ 326건, Native 280 × 0.825 = 231건(29% 낮음), req/s × (1 − fail%)로는 JVM 2.61 × 0.997 ≈ 2.60, Native 2.09 × 0.825 ≈ 1.72(34% 낮음)이다. 두 방식이 다른 것은 원문 표의 total ÷ req/s가 JVM 약 125초, Native 약 134초로 측정 시간이 달라서다. 원문 수치와 "~20% 느림"은 고치지 않았다.
- 측정 계획(future-work)의 `/db` 테스트는 결과에 없다.
