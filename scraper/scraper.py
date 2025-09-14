import json
import os
import psycopg
import requests
import time

from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any, List


load_dotenv()

conn = psycopg.connect(os.getenv("DATABASE_URL"))


PERIOD_API_URL = f"https://{os.getenv('BASE_API_URL')}/locations/5b50c589f3eeb609b36a87eb/periods/?date=%s"
API_URL = f"https://{os.getenv('BASE_API_URL')}/locations/5b50c589f3eeb609b36a87eb/menu?period=%s&date=%s"
MEAL_TYPES = set(["breakfast", "lunch", "dinner"])

START_DATE = datetime(2025, 9, 16).date()
END_DATE = datetime(2025, 9, 17).date()


def add_item(item_data: Dict[str, Any]) -> None:
    nutrients = {
        nutrient_data["name"].split(" (")[0].strip(): nutrient_data["valueNumeric"].strip() + nutrient_data["uom"].strip()
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
                 item_data["ingredients"].strip().replace("^", ""), json.dumps(nutrients), json.dumps(filters))
            )

        conn.commit()
    except psycopg.IntegrityError:
        conn.rollback()
    except Exception as e:
        conn.rollback()
        print('Error adding item:', e)

def add_menu(date: str, meal: str, location: str, status: str) -> int:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO menus (date, meal, location, status) VALUES (%s, %s, %s, %s) RETURNING ID;",
                (date, meal, location, status)
            )
            value = cur.fetchone()[0]
    
        conn.commit()
        return value
    except Exception as e:
        conn.rollback()
        print('Error adding menu:', e)
        return None

def add_menu_items(menu_id: int, items: List[str]) -> None:
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO menu_items VALUES (%s, %s)
                   ON CONFLICT (menu_id, item_name) DO NOTHING;""",
                [(menu_id, item) for item in items]
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print('Error adding menu items:', e)


def scrape_menus(date: str, refresh_menus: bool = False) -> bool:
    """
    Scrapes breakfast, lunch, and dinner menus for a given date.
    Inserts items, locations, and menus into the database.
    
    Args:
        date: Date string in YYYY-MM-DD format
        refresh_menus: If True, clears existing menu data for the date before scraping
    """

    response = requests.get(
        PERIOD_API_URL % (date),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        },
        timeout=5
    )

    data = response.json()
    
    if refresh_menus:
        if "periods" not in data:
            raise Exception(f"No periods found for {date}")

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM menu_items 
                    WHERE menu_id IN (
                        SELECT id FROM menus WHERE date = %s
                    );
                """, (date,))
                
                cur.execute("DELETE FROM menus WHERE date = %s;", (date,))
            
            conn.commit()
            print(f"Cleared existing menu data for {date}")
        except Exception as e:
            conn.rollback()
            print(f'Error clearing menu data for {date}:', e)

    # Closed
    if not data["periods"]:
        print(f"No periods found for {date}")
        for meal_type in MEAL_TYPES:
            add_menu(date, meal_type, None, "closed")
    
        return

    meals = {
        period["id"]: period["slug"]
        for period in data["periods"]
        if period["slug"] in MEAL_TYPES
    }
    
    for meal_hash, meal_type in meals.items():
        response = requests.get(
            API_URL % (meal_hash, date),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            },
            timeout=5
        )

        data = response.json()
        
        for location_data in data["period"]["categories"]:
            items = []
            for item_data in location_data["items"]:
                item_data["name"] = item_data["name"].strip()
                add_item(item_data)
                items.append(item_data["name"])
            
            menu_id = add_menu(date, meal_type, location_data["name"], "open")

            add_menu_items(menu_id, items)     
            
            print(f"Added menu for {date} {meal_type} {location_data['name']}")

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
    main()

    conn.close()
