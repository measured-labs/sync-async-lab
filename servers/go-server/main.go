package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"time"

	_ "github.com/lib/pq"
	"golang.org/x/net/websocket"
)

var db *sql.DB

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

func dbHandler(w http.ResponseWriter, r *http.Request) {
	_, err := db.Exec("SELECT pg_sleep(0.2)")
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"server":   "go-goroutine",
		"type":     "db",
		"delay_ms": 200,
	})
}

func wsHandler(ws *websocket.Conn) {
	defer ws.Close()
	buf := make([]byte, 4096)
	for {
		n, err := ws.Read(buf)
		if err != nil {
			return
		}
		_, err = ws.Write(buf[:n])
		if err != nil {
			return
		}
	}
}

func main() {
	dbHost := os.Getenv("DB_HOST")
	if dbHost == "" {
		dbHost = "postgres"
	}
	var err error
	db, err = sql.Open("postgres", "host="+dbHost+" port=5432 user=bench password=bench dbname=bench sslmode=disable")
	if err == nil {
		db.SetMaxOpenConns(20)
		db.SetMaxIdleConns(5)
	}

	http.HandleFunc("/io", ioHandler)
	http.HandleFunc("/cpu", cpuHandler)
	http.HandleFunc("/db", dbHandler)
	http.Handle("/ws", &websocket.Server{Handler: wsHandler})
	http.ListenAndServe(":8080", nil)
}
