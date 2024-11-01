package scraper

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/valyala/fasthttp"

	"github.com/kevintsoii/SJSU-Eats-Backend/internal/db"
)

const (
	APIURL    = "https://api.dineoncampus.com/v1/location/5b50c589f3eeb609b36a87eb/periods/%s?platform=0&date=%s"
	UserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)

var mealTypes = map[string]string{
	"66bf79f3351d5300dd055257": "breakfast",
	"66bf7d21e45d430859cf99b2": "lunch",
	"66bf7d21e45d430859cf99b8": "dinner",
}

type Response struct {
	Closed bool `json:"closed"`
	Menu   struct {
		Periods struct {
			Categories []struct {
				Name  string `json:"name"`
				Items []struct {
					Name        string `json:"name"`
					Desc        string `json:"desc"`
					Portion     string `json:"portion"`
					Ingredients string `json:"ingredients"`
					Calories    string `json:"calories"`
					Nutrients   []struct {
						Name          string `json:"name"`
						Value_Numeric string `json:"value_numeric"`
						UOM           string `json:"uom"`
					} `json:"nutrients"`
					Filters []struct {
						Name string `json:"name"`
						Type string `json:"type"`
					} `json:"filters"`
				} `json:"items"`
			} `json:"categories"`
		} `json:"periods"`
	} `json:"menu"`
}

var saveMutex sync.Mutex

func get(date string, meal string, wg *sync.WaitGroup) {
	defer wg.Done()
	url := fmt.Sprintf(APIURL, meal, date)

	req := fasthttp.AcquireRequest()
	defer fasthttp.ReleaseRequest(req)

	req.SetRequestURI(url)
	req.Header.SetMethod("GET")
	req.Header.Set("User-Agent", UserAgent)

	resp := fasthttp.AcquireResponse()
	defer fasthttp.ReleaseResponse(resp)

	err := fasthttp.DoTimeout(req, resp, 30*time.Second)
	if err != nil {
		log.Printf("error fetching URL: %v", err)
		return
	}

	var data Response
	if err := json.Unmarshal(resp.Body(), &data); err != nil {
		log.Printf("error parsing JSON: %v", err)
		return
	}

	if err := Save(&data, date, mealTypes[meal]); err != nil {
		log.Printf("error saving data: %v", err)
		return
	}
}

func Scrape(date string) error {
	var wg sync.WaitGroup

	for meal := range mealTypes {
		wg.Add(1)
		go get(date, meal, &wg)
	}

	wg.Wait()
	return nil
}

func Save(data *Response, date string, meal string) error {
	saveMutex.Lock()
	defer saveMutex.Unlock()

	conn := db.GetDB()
	if conn == nil {
		return fmt.Errorf("database connection is nil")
	}

	// Check if menu already exists
	var count int
	err := conn.QueryRow("SELECT COUNT(*) FROM Menus WHERE date = @p1 AND meal = @p2", date, meal).Scan(&count)
	if err != nil {
		return fmt.Errorf("error querying database: %v", err)
	}
	if count > 0 {
		return nil
	}

	// Handle closed day
	if data.Closed {
		_, err := conn.Exec("INSERT INTO Menus (date, meal) VALUES (@p1, @p2)", date, meal)
		if err != nil {
			return fmt.Errorf("error inserting into Menus: %v", err)
		}
		log.Printf("Saved (closed): %s %s", date, meal)
		return nil
	}

	// Begin transaction
	tx, err := conn.Begin()
	if err != nil {
		return fmt.Errorf("error beginning transaction: %v", err)
	}

	defer func() {
		if err != nil {
			tx.Rollback()
		} else {
			tx.Commit()
		}
	}()

	// Menus shows that the date is saved
	var menuID int
	err = tx.QueryRow("INSERT INTO Menus (date, meal) OUTPUT INSERTED.id VALUES (@p1, @p2)", date, meal).Scan(&menuID)
	if err != nil {
		return fmt.Errorf("failed to insert into Menus: %v", err)
	}

	// Add Menu Items
	for _, category := range data.Menu.Periods.Categories {
		location := strings.TrimSpace(category.Name)

		if len(category.Items) == 0 {
			continue
		}

		for _, item := range category.Items {
			item.Name = strings.TrimSpace(item.Name)

			nutrients := make(map[string]string)
			for _, nutrient := range item.Nutrients {
				nutrient.Value_Numeric = strings.TrimSpace(nutrient.Value_Numeric)
				if nutrient.Value_Numeric == "0" || nutrient.Value_Numeric == "-" {
					continue
				}

				nameParts := strings.SplitN(nutrient.Name, " (", 2)
				value := nutrient.Value_Numeric + strings.TrimSpace(nutrient.UOM)
				nutrients[strings.TrimSpace(nameParts[0])] = value
			}

			nutrientsJSON, err := json.Marshal(nutrients)
			if err != nil {
				return fmt.Errorf("failed to marshal nutrients to JSON: %v", err)
			}

			filters := []string{}
			for _, filter := range item.Filters {
				if strings.TrimSpace(filter.Type) == "label" {
					filters = append(filters, strings.TrimSpace(filter.Name))
				}
			}

			filtersJSON, err := json.Marshal(filters)
			if err != nil {
				return fmt.Errorf("failed to marshal filters to JSON: %v", err)
			}

			_, err = tx.Exec(`
				IF NOT EXISTS (SELECT 1 FROM Items WHERE name = @p1)
				BEGIN
					INSERT INTO Items (name, description, portion, ingredients, nutrients, filters, image_url, image_source)
					VALUES (@p1, @p2, @p3, @p4, @p5, @p6, @p7, @p8)
				END;
			`, item.Name, strings.TrimSpace(item.Desc), strings.TrimSpace(item.Portion), strings.TrimSpace(item.Ingredients), string(nutrientsJSON), string(filtersJSON), nil, nil)

			if err != nil {
				return fmt.Errorf("failed to insert into Items: %v", err)
			}

			_, err = tx.Exec(`
				INSERT INTO dbo.MenuItems (menu_id, item_name, location) VALUES (@p1, @p2, @p3)
			`, menuID, item.Name, location)

			if err != nil {
				return fmt.Errorf("failed to insert into MenuItems: %v", err)
			}
		}
	}

	log.Printf("Saved: %s %s", date, meal)

	return nil
}
