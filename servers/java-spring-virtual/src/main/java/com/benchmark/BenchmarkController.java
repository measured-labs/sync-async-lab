package com.benchmark;

import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class BenchmarkController {

    @Autowired(required = false)
    private JdbcTemplate jdbcTemplate;

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

    @GetMapping("/db")
    public Map<String, Object> db() {
        jdbcTemplate.execute("SELECT pg_sleep(0.2)");
        return Map.of("server", "spring-virtual", "type", "db", "delay_ms", 200);
    }

    private long fibonacci(int n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}
