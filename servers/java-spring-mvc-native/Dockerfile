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

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=build /app/build/native/nativeCompile/spring-mvc-native .
EXPOSE 8080
CMD ["./spring-mvc-native"]
