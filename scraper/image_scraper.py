import os
import hashlib

import psycopg2
import requests
from psycopg2 import extras
from dotenv import load_dotenv


API_URL = "https://customsearch.googleapis.com/customsearch/v1?key=%s&cx=%s&searchType=image&fileType=jpg&q=%s" \
          "&siteSearch=www.alamy.com&siteSearchFilter=e"

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
cur = conn.cursor(cursor_factory=extras.RealDictCursor)

GOOGLE_IMAGES_API_KEY = os.getenv("GOOGLE_IMAGES_API_KEY")
GOOGLE_IMAGES_CSE_ID = os.getenv("GOOGLE_IMAGES_CSE_ID")


def scrape_image(item_name: str, offset: bool=False) -> str:
    if offset:
        response = requests.get(API_URL % (GOOGLE_IMAGES_API_KEY, GOOGLE_IMAGES_CSE_ID, item_name + " plated food image"), timeout=15)
    else:
        response = requests.get(API_URL % (GOOGLE_IMAGES_API_KEY, GOOGLE_IMAGES_CSE_ID, item_name + " plated food image") + "&start=11", timeout=15)
    if "items" not in response.json():
        print("Error:", response.json())
        return ""

    image_data = None
    for image in response.json()["items"]:
        image_link = image["link"]
        try:
            image_response = requests.get(image_link, timeout=5)
        except:
            continue

        if image_response.status_code == 200:
            image_data = image_response.content
            break
        print(f"Invalid Image: {image['link']}")
    
    if image_data is None:
        if not offset:
            return scrape_image(item_name, True)
        return ""
    
    image_name = hashlib.md5(item_name.encode()).hexdigest() + ".jpg"
    with open(f"src/assets/images/{image_name}", "wb") as image_file:
        image_file.write(image_data)
    print(f"Image saved: {image_name}.")
    cur.execute("UPDATE items SET image = %s, image_source = %s WHERE name = %s;", (image_name, image_link, item_name))

    return image_name


def scrape_all_images() -> None:
    cur.execute("SELECT name FROM items WHERE image IS NULL;")
    rows = cur.fetchall()

    print(f"Scraping images for {len(rows)} items.")
    for row in rows:
        print(f"Scraping image for {row['name']}.")
        scrape_image(row["name"])


def main():
    scrape_all_images()


if __name__ == "__main__":
    main()
