package scraper

import (
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/joho/godotenv"
	"github.com/valyala/fasthttp"
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

func Save(response *Response, date string, meal string) error {
	err := godotenv.Load(".env")
	if err != nil {
		log.Fatal("Error loading .env file")
		return nil
	}
	// *********** IMPLEMENT DATABASE***********

	data := *response
	if data.Closed {
		log.Printf("Closed")
		return nil
	}

	for _, restaurant := range data.Menu.Periods.Categories {
		for _, item := range restaurant.Items {
			for _, nutrient := range item.Nutrients {
				//log.Printf("Nutrient: %s %s %s", nutrient.Name, nutrient.Value_Numeric, nutrient.UOM)
				_ = nutrient
			}
			for _, filter := range item.Filters {
				//log.Printf("Filter: %s %s", filter.Name, filter.Type)
				_ = filter
			}
			log.Print(meal)
		}
	}

	return nil
}
