package main

import (
	"encoding/json"
	"net/http"
	"time"
)

func fibonacci(n int) int {
	if n <= 1 {
		return n
	}
	return fibonacci(n-1) + fibonacci(n-2)
}

func ioHandler(w http.ResponseWriter, r *http.Request) {
	time.Sleep(200 * time.Millisecond)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"server":   "go-goroutine",
		"type":     "io",
		"delay_ms": 200,
	})
}

func cpuHandler(w http.ResponseWriter, r *http.Request) {
	result := fibonacci(38)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"server":    "go-goroutine",
		"type":      "cpu",
		"fibonacci": result,
	})
}

func main() {
	http.HandleFunc("/io", ioHandler)
	http.HandleFunc("/cpu", cpuHandler)
	http.ListenAndServe(":8080", nil)
}
