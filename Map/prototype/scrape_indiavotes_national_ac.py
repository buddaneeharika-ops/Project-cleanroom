import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Hand-compiled dictionary of the most recent Vidhan Sabha (State Assembly) 
# Election URLs from IndiaVotes to bypass the blocked index page scraping.
STATE_ELECTION_URLS = {
    "Andhra Pradesh": "https://www.indiavotes.com/vidhan-sabha/2019/andhra-pradesh/269/41",
    "Arunachal Pradesh": "https://www.indiavotes.com/vidhan-sabha/2019/arunachal-pradesh/270/46",
    "Assam": "https://www.indiavotes.com/vidhan-sabha/2021/assam/280/42",
    "Bihar": "https://www.indiavotes.com/vidhan-sabha/2020/bihar/275/43",
    "Chhattisgarh": "https://www.indiavotes.com/vidhan-sabha/2023/chhattisgarh/293/54",
    "Delhi": "https://www.indiavotes.com/vidhan-sabha/2020/delhi/274/53",
    "Goa": "https://www.indiavotes.com/vidhan-sabha/2022/goa/285/47",
    "Gujarat": "https://www.indiavotes.com/vidhan-sabha/2022/gujarat/290/48",
    "Haryana": "https://www.indiavotes.com/vidhan-sabha/2019/haryana/273/45",
    "Himachal Pradesh": "https://www.indiavotes.com/vidhan-sabha/2022/himachal-pradesh/289/49",
    "Jharkhand": "https://www.indiavotes.com/vidhan-sabha/2019/jharkhand/272/55",
    "Karnataka": "https://www.indiavotes.com/vidhan-sabha/2023/karnataka/291/56",
    "Kerala": "https://www.indiavotes.com/vidhan-sabha/2021/kerala/279/57",
    "Madhya Pradesh": "https://www.indiavotes.com/vidhan-sabha/2023/madhya-pradesh/292/58",
    "Maharashtra": "https://www.indiavotes.com/vidhan-sabha/2019/maharashtra/271/59",
    "Manipur": "https://www.indiavotes.com/vidhan-sabha/2022/manipur/286/60",
    "Meghalaya": "https://www.indiavotes.com/vidhan-sabha/2023/meghalaya/294/61",
    "Mizoram": "https://www.indiavotes.com/vidhan-sabha/2023/mizoram/295/62",
    "Nagaland": "https://www.indiavotes.com/vidhan-sabha/2023/nagaland/296/63",
    "Odisha": "https://www.indiavotes.com/vidhan-sabha/2019/odisha/268/64",
    "Punjab": "https://www.indiavotes.com/vidhan-sabha/2022/punjab/284/65",
    "Rajasthan": "https://www.indiavotes.com/vidhan-sabha/2023/rajasthan/297/66",
    "Sikkim": "https://www.indiavotes.com/vidhan-sabha/2019/sikkim/267/67",
    "Tamil Nadu": "https://www.indiavotes.com/vidhan-sabha/2021/tamil-nadu/277/68",
    "Telangana": "https://www.indiavotes.com/vidhan-sabha/2023/telangana/298/69",
    "Tripura": "https://www.indiavotes.com/vidhan-sabha/2023/tripura/299/70",
    "Uttar Pradesh": "https://www.indiavotes.com/vidhan-sabha/2022/uttar-pradesh/287/71",
    "Uttarakhand": "https://www.indiavotes.com/vidhan-sabha/2022/uttarakhand/288/72",
    "West Bengal": "https://www.indiavotes.com/vidhan-sabha/2021/west-bengal/281/73"
}

def scrape_state_assembly(state_name, url, driver):
    print(f"Scraping {state_name}...")
    driver.get(url)
    
    # Wait for the table to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "table-bordered"))
        )
        
        # Try to select 'All' from the dropdown to show all ACs on one page
        try:
            select_element = driver.find_element(By.NAME, "DataTables_Table_0_length")
            for option in select_element.find_elements(By.TAG_NAME, 'option'):
                if option.text == 'All' or option.get_attribute('value') == '-1':
                    option.click()
                    time.sleep(2) # wait for re-render
                    break
        except Exception as e:
            print("  -> Could not find 'All' dropdown, proceeding with visible rows.")
            
    except Exception as e:
        print(f"  -> Timeout waiting for {state_name} table.")
        
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Finding the main result table which usually has class 'table table-bordered'
    table = soup.find('table', class_='table-bordered')
    
    if not table:
        print(f"  -> Failed to find table for {state_name}")
        return []
        
    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else []
    
    election_data = []
    
    for row in rows:
        cols = row.find_all('td')
        
        # We need to handle variations in columns across years (e.g. 2023 added District)
        # SNo | AC Name | AC No | Type | District (Optional) | Winner | Party | Electors | Votes | Turnout | Margin | Margin %
        
        if len(cols) >= 10:
            # Detect if 'District' column exists by checking Type column contents
            # Type is usually GEN, SC, ST
            type_val = cols[3].text.strip()
            
            offset = 1 if len(cols) >= 12 else 0 # Offset if district exists
            
            try:
                record = {
                    "state": state_name,
                    "id": cols[0].text.strip(),
                    "ac_name": cols[1].text.strip(),
                    "ac_no": cols[2].text.strip(),
                    "type": type_val,
                    "winner": cols[4+offset].text.strip(),
                    "party": cols[5+offset].text.strip(),
                    "electors": cols[6+offset].text.strip().replace(',', ''),
                    "votes": cols[7+offset].text.strip().replace(',', ''),
                    "turnout": cols[8+offset].text.strip(),
                    "margin": cols[9+offset].text.strip().replace(',', '')
                }
                
                if len(cols) > (10+offset):
                    record["margin_percent"] = cols[10+offset].text.strip()
                else:
                    record["margin_percent"] = "N/A"
                    
                election_data.append(record)
            except IndexError:
                continue

    print(f"  -> Extracted {len(election_data)} records for {state_name}")
    return election_data

def compile_national_ac_data():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    all_data = []
    
    try:
        for state, url in STATE_ELECTION_URLS.items():
            results = scrape_state_assembly(state, url, driver)
            all_data.extend(results)
    finally:
        driver.quit()
        
    output_path = r"d:\Others\Varahe Work\Project Mapping UI\election-lens\public\data\ac_boundaries\india_ac_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4)
        
    print(f"\nCompleted! Scraped {len(all_data)} total ACs nationwide.")
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    compile_national_ac_data()
