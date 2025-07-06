import os
import json
import requests
from datetime import date
from bs4 import BeautifulSoup

def process_url(url):
    if url and url.startswith("../"):
        return "https://loyolacollege.edu" + url[2:]
    elif url and url.startswith("../../"):
        return "https://loyolacollege.edu" + url[3:]
    return url

url = "https://loyolacollege.edu/"

try:
    response = requests.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        partner_wrapper = soup.find('div', class_='partner-wrapper hero-slider owl-carousel owl-theme')
        
        if partner_wrapper:
            list_items = partner_wrapper.find_all('li')
            
            data = []
            data_file = 'data/flash_news.json'

            existing_data = []
            if os.path.isfile(data_file):
                with open(data_file, 'r') as file:
                    existing_data = json.load(file)
            
            print("\nExtracted Data:")
            print("----------------")
            
            for index, item in enumerate(list_items):
                serial_number = index + 1
                
                notice = item.get_text(strip=True)
                
                link = item.find('a')
                
                raw_url = link.get('href') if link else None
                processed_url = process_url(raw_url)
                
                today = date.today().strftime("%Y-%m-%d")
                
                item_data = {
                    "serial_number": serial_number,
                    "notice": notice,
                    "date": today,
                    "url": processed_url
                }

                is_duplicate = any(
                    d['notice'] == notice and d['date'] == today
                    for d in existing_data
                )
                
                if not is_duplicate:
                    print(f"Serial Number: {serial_number}")
                    print(f"Notice: {notice}")
                    print(f"Date: {today}")
                    print(f"URL: {processed_url}")
                    print("----------------")
                    
                    data.append(item_data)
                    existing_data.append(item_data)
                else:
                    print(f"Skipping duplicate: Notice - '{notice}' on {today}")
            
            os.makedirs('data', exist_ok=True)

            with open(data_file, 'w') as file:
                json.dump(existing_data, file, indent=4)
            
            print(f"\nData has been printed above and saved to {data_file}")
            print(f"Total unique messages: {len(existing_data)}")
        else:
            print("No div with class 'partner-wrapper hero-slider owl-carousel owl-theme' found.")
    else:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
except Exception as e:
    print(f"An error occurred: {e}")