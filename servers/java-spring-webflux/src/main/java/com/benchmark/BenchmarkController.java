package com.benchmark;

import java.time.Duration;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import reactor.core.publisher.Mono;

@RestController
public class BenchmarkController {

    @GetMapping("/io")
    public Mono<Map<String, Object>> io() {
        return Mono.delay(Duration.ofMillis(200))
                .thenReturn(Map.of(
                        "server", "spring-webflux",
                        "type", "io",
                        "delay_ms", 200
                ));
    }

    @GetMapping("/cpu")
    public Mono<Map<String, Object>> cpu() {
        return Mono.fromCallable(() -> {
            long result = fibonacci(38);
            return Map.<String, Object>of(
                    "server", "spring-webflux",
                    "type", "cpu",
                    "fibonacci", result
            );
        });
    }

    private long fibonacci(int n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}
