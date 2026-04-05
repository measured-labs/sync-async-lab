package com.benchmark;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class BenchmarkController {

    @GetMapping("/io")
    public Map<String, Object> io() throws InterruptedException {
        Thread.sleep(200);
        return Map.of(
            "server", "spring-virtual",
            "type", "io",
            "delay_ms", 200
        );
    }

    @GetMapping("/cpu")
    public Map<String, Object> cpu() {
        long result = fibonacci(38);
        return Map.of(
            "server", "spring-virtual",
            "type", "cpu",
            "fibonacci", result
        );
    }

    private long fibonacci(int n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}
