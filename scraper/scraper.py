import os
import json
import time
from typing import Dict, Any
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


load_dotenv()


API_URL = f"https://{os.getenv('BASE_API_URL')}/locations/5b50c589f3eeb609b36a87eb/menu?period=%s&date=%s"
MEAL_TYPES = {
    "68b686b6bb032e612d4fa1ad": "breakfast",
    "68b686b6bb032e612d4fa1ab": "lunch",
    "68b686b6bb032e612d4fa1ac": "dinner"
}

START_DATE = datetime(2025, 1, 1).date()
END_DATE = datetime(2025, 5, 31).date()


def add_item(item_data: Dict[str, Any]) -> None:
    nutrients = {
        nutrient_data["name"].split(" (")[0].strip(): nutrient_data["value_numeric"].strip() + nutrient_data["uom"].strip()
        for nutrient_data in item_data["nutrients"]
    }
    filters = [
        filter_data["name"].strip()
        for filter_data in item_data["filters"]
        if filter_data["type"] == "label"
    ]

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO items VALUES (%s, %s, %s, %s, %s, %s);",
                (item_data["name"],
                 item_data["desc"].strip() if item_data["desc"] is not None else None,
                 item_data["portion"].strip() if item_data["portion"] is not None else None,
                 item_data["ingredients"].strip(), json.dumps(nutrients), json.dumps(filters))
            )

        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()

def add_menu(date: str, meal: str, location: str, status: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO menus (date, meal, location, status) VALUES (%s, %s, %s, %s) RETURNING ID;",
            (date, meal, location, status)
        )
        return cur.fetchone()[0]

def scrape_menus(date: str) -> bool:
    """
    Scrapes breakfast, lunch, and dinner menus for a given date.
    Inserts items, locations, and menus into the database.
    """
    for meal_hash, meal_type in MEAL_TYPES.items():
        driver.get(API_URL % (meal_hash, date))
        json_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "pre"))
        )
        data = json.loads(json_element.text)
        
        if data["closed"]:
            try:
                add_menu(date, meal_type, None, "closed")
                conn.commit()
            except Exception as e:
                conn.rollback()
                print('Error adding closed menu:', e)
            continue

        
        for location_data in data["menu"]["periods"]["categories"]:
            items = []
            for item_data in location_data["items"]:
                item_data["name"] = item_data["name"].strip()
                add_item(item_data)
                items.append(item_data["name"])
            
            try:
                menu_id = add_menu(date, meal_type, location_data["name"], "open")

                with conn.cursor() as cur:
                    menu_items = [(menu_id, item) for item in items]
                    cur.executemany(
                        "INSERT INTO menu_items VALUES (%s, %s);",
                        menu_items
                    )
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                print('Error adding menu:', e)

def main():
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM menus
            WHERE date = (SELECT MAX(date) FROM menus);
        """)

        cur.execute("""
            SELECT DISTINCT date FROM menus;
        """)
        scraped_dates = {row[0] for row in cur.fetchall()}

    conn.commit()

    all_dates = {START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days)}
    missing_dates = sorted(all_dates - scraped_dates)
   
    for current_date in missing_dates:
        print(f'Obtaining menus for {current_date.strftime("%Y-%m-%d")}.')
        scrape_menus(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
        time.sleep(5)


if __name__ == "__main__":
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))

    options = Options()
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)

    main()

    conn.close()
    driver.quit()
