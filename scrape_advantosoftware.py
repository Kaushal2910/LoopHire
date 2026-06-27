import os
import json
import requests
from bs4 import BeautifulSoup

def main():
    url = "https://advantosoftware.com/job-openings-for-our-students-page-6/"
    print(f"Fetching Advanto Software jobs from: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[Error] Failed to fetch Advanto Software page: {e}")
        return

    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    if not tables:
        print("[Error] No job table found on the page.")
        return
        
    table = tables[0]
    rows = table.find_all('tr')
    print(f"Found {len(rows) - 1} job listings in the table.")
    
    scraped_jobs = []
    
    for row in rows[1:]: # Skip header row
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 6:
            role = cells[1].get_text(strip=True)
            company = cells[2].get_text(strip=True)
            package = cells[3].get_text(strip=True)
            experience = cells[4].get_text(strip=True)
            
            # Find detail/application link
            link_el = cells[5].find('a')
            apply_url = link_el['href'] if link_el and link_el.has_attr('href') else url
            
            # Construct description from package and experience metadata
            description = (
                f"Job Role: {role}\n"
                f"Company: {company}\n"
                f"Salary Package: {package}\n"
                f"Required Experience: {experience}\n"
                f"Source: Advanto Software Student Job Openings."
            )
            
            scraped_jobs.append({
                "title": role,
                "company": company,
                "description": description,
                "apply_url": apply_url,
                "source": "Advanto Software"
            })
            
    # Load existing jobs to prevent duplicates
    output_path = "jobs_data.json"
    existing_jobs = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_jobs = json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to load existing jobs: {e}")

    existing_keys = {
        (j.get("title", "").strip().lower(), j.get("company", "").strip().lower())
        for j in existing_jobs
    }

    new_jobs_added = 0
    for job in scraped_jobs:
        key = (job["title"].strip().lower(), job["company"].strip().lower())
        if key not in existing_keys:
            existing_jobs.append(job)
            existing_keys.add(key)
            new_jobs_added += 1
            print(f"  -> Added new job: {job['title']} at {job['company']}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_jobs, f, indent=4, ensure_ascii=False)
        
    print(f"\n[Advanto Scraper Complete] Added {new_jobs_added} new jobs. Total jobs in list: {len(existing_jobs)}")

if __name__ == '__main__':
    main()
