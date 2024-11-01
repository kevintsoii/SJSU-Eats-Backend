package main

import (
	"log"
	"sync"
	"time"

	"github.com/kevintsoii/SJSU-Eats-Backend/internal/db"
	"github.com/kevintsoii/SJSU-Eats-Backend/internal/scraper"
)

type Task struct {
	Date time.Time
}

func worker(tasks <-chan Task, wg *sync.WaitGroup) {
	defer wg.Done()

	for task := range tasks {
		err := scraper.Scrape(task.Date.Format("2006-01-02"))
		if err != nil {
			log.Printf("Error scraping data: %+v", err)
		}
		time.Sleep(5 * time.Second)
	}
}

func main() {
	err := db.Init()
	if err != nil {
		log.Fatalf("Error initializing database: %v", err)
	}

	var wg sync.WaitGroup
	tasks := make(chan Task, 5)

	// Start worker pool
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go worker(tasks, &wg)
	}

	// Create a task for each date and meal type
	start := time.Date(2024, 10, 27, 0, 0, 0, 0, time.UTC)
	end := time.Date(2024, 10, 28, 0, 0, 0, 0, time.UTC)

	for date := start; date.Before(end); date = date.AddDate(0, 0, 1) {
		tasks <- Task{date}
	}
	close(tasks)

	wg.Wait()
	log.Println("Scraping complete!")
}
