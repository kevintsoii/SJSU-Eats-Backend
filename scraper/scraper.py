import os
import json
import time
from typing import Dict, Any
from datetime import datetime, timedelta

import psycopg2
import requests
from dotenv import load_dotenv


API_URL = "https://api.dineoncampus.com/v1/location/5b50c589f3eeb609b36a87eb/periods/%s?platform=0&date=%s"
MEAL_TYPES = {
    "66bf79f3351d5300dd055257": "breakfast",
    "66bf7d21e45d430859cf99b2": "lunch",
    "66bf7d21e45d430859cf99b8": "dinner"
}

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
cur = conn.cursor()

found_items = set()
found_locations = set()


def add_item(item_data: Dict[str, Any]) -> None:
    if item_data["name"] in found_items:
        return
    
    nutrients = {
        nutrient_data["name"].split(" (")[0]: nutrient_data["value_numeric"] + nutrient_data["uom"]
        for nutrient_data in item_data["nutrients"]
    }
    filters = [
        filter_data["name"]
        for filter_data in item_data["filters"]
        if filter_data["type"] == "label"
    ]
    try:
        cur.execute(
            "INSERT INTO items VALUES (%s, %s, %s, %s, %s, %s);",
            (item_data["name"], item_data["desc"], item_data["portion"],
             item_data["ingredients"], json.dumps(nutrients), json.dumps(filters))
        )
        print(f'Added new item: {item_data["name"]}.')
    except psycopg2.IntegrityError:
        pass

    found_items.add(item_data["name"])


def add_location(location_data: Dict[str, Any]) -> None:
    if location_data["name"] in found_locations:
        return
    
    try:
        cur.execute(
            "INSERT INTO locations (name) VALUES (%s);",
            (location_data["name"], )
        )
        print(f'Added new location: {location_data["name"]}.')
    except psycopg2.IntegrityError:
        pass

    found_locations.add(location_data["name"])


def scrape_menus(date: str) -> bool:
    """
    Scrapes breakfast, lunch, and dinner menus for a given date.
    Inserts items, locations, and menus into the database.
    """
    scraped = False

    for meal_hash, meal_type in MEAL_TYPES.items():
        response = requests.get(
            API_URL % (meal_hash, date),
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
            }
        )
        data = response.json()
        
        if data["closed"]:
            continue

        for location_data in data["menu"]["periods"]["categories"]:
            items = []
            add_location(location_data)
            for item_data in location_data["items"]:
                add_item(item_data)
                items.append(item_data["name"])
            
            try:
                cur.execute(
                    "INSERT INTO menus VALUES (%s, %s, %s, %s)",
                    (date, meal_type, location_data["name"], items)
                )
                scraped = True
            except psycopg2.IntegrityError:
                pass
            conn.commit()
    
    return scraped


def main():
    current_date = datetime(2024, 3, 20)
    end_date = datetime(2024, 5, 31)
    
    while current_date < end_date:
        print(f'Obtaining menus for {current_date.strftime("%Y-%m-%d")}.')
        scrape_menus(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
        time.sleep(5)
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
