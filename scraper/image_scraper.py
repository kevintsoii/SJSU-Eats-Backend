import os
import hashlib
from io import BytesIO

import boto3
import psycopg
import requests
from dotenv import load_dotenv


load_dotenv()

API_URL = "https://customsearch.googleapis.com/customsearch/v1?key=%s&cx=%s&searchType=image&fileType=jpg&q=%s" \
          "&siteSearch=www.alamy.com&siteSearchFilter=e"

GOOGLE_IMAGES_API_KEY = os.getenv("GOOGLE_IMAGES_API_KEY")
GOOGLE_IMAGES_CSE_ID = os.getenv("GOOGLE_IMAGES_CSE_ID")

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("SECRET_ACCESS_KEY")
)

conn = psycopg.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
cur = conn.cursor(row_factory=psycopg.rows.dict_row)


def scrape_image(item_name: str, offset: bool=False) -> str:
    url = API_URL % (GOOGLE_IMAGES_API_KEY, GOOGLE_IMAGES_CSE_ID, item_name + " plated food image")
    if offset:
       url += "&start=11"
    response = requests.get(url, timeout=15)

    if "items" not in response.json():
        print(f"Error ({item_name}):", response.json())
        return ""

    image_data = None
    for image in response.json()["items"]:
        image_link = image["link"]

        try:
            image_response = requests.get(image_link, timeout=5)
            if image_response.status_code == 200:
                image_data = BytesIO(image_response.content)
                break
        except:
            continue
    
    if image_data is None:
        if not offset:
            return scrape_image(item_name, True)
        return ""
    
    image_name = hashlib.md5(item_name.encode()).hexdigest()
    s3_client.upload_fileobj(image_data, os.getenv("R2_BUCKET_NAME"), image_name, ExtraArgs={"ACL": "public-read"})
    public_url = f"{os.getenv('R2_PUBLIC_URL')}/{image_name}"
    print(f"Added: {public_url}")

    cur.execute("UPDATE items SET image = %s, image_source = %s WHERE name = %s;", (public_url, image_link, item_name))
    return image_name


def scrape_all_images() -> None:
    cur.execute("SELECT name FROM items WHERE image IS NULL;")
    rows = cur.fetchall()

    print(f"Scraping images for {len(rows)} items.")
    for row in rows:
        scrape_image(row["name"])


def main():
    scrape_all_images()


if __name__ == "__main__":
    main()
