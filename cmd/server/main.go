package main

import (
	"log"

	"github.com/kevintsoii/SJSU-Eats-Backend/internal/db"
)

func main() {
	err := db.Init()
	if err != nil {
		log.Fatalf("Error initializing database: %v", err)
	}
	defer db.Close()
}
