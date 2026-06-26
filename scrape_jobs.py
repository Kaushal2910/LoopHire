import subprocess
import time
import json
import sys

def run_cli_cmd(args):
    # Run a browser-act CLI command and return stdout
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    return result.stdout.strip()

def main():
    print("Starting BrowserAct Chrome session...")
    # Start the browser open process in background to keep it alive
    browser_proc = subprocess.Popen([
        "browser-act", "browser", "open", "chrome_local_103775758939324604",
        "https://www.linkedin.com/jobs/search/?keywords=developer&location=Pune&f_E=1",
        "--allow-restart-chrome", "--session", "linkedin_session"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for the browser and page to load
    print("Waiting 10 seconds for LinkedIn to load and authenticate...")
    time.sleep(10)
    
    # Let's scroll the job list container to load more items
    print("Scrolling job list to load entries...")
    scroll_js = """
    const el = document.querySelector('.jobs-search-results-list');
    if (el) {
        el.scrollTop = el.scrollHeight;
        'scrolled'
    } else {
        'no list'
    }
    """
    for _ in range(3):
        run_cli_cmd(["browser-act", "--session", "linkedin_session", "eval", scroll_js])
        time.sleep(2)

    # Get total job cards count
    count_js = "document.querySelectorAll('.job-card-container a[aria-label]').length"
    count_str = run_cli_cmd(["browser-act", "--session", "linkedin_session", "eval", count_js])
    try:
        count = int(count_str.split('\n')[-1].strip())
    except Exception:
        count = 0
        
    print(f"Found {count} jobs on the page.")
    if count == 0:
        print("No job cards found. Exiting.")
        browser_proc.terminate()
        return

    jobs_data = []
    
    # Scrape each job card (limit to 10 to make it fast and avoid rate limits)
    max_to_scrape = min(count, 10)
    print(f"Scraping the latest {max_to_scrape} jobs...")
    
    for i in range(max_to_scrape):
        print(f"Processing job {i+1}/{max_to_scrape}...")
        
        # Click the i-th job card
        click_js = f"document.querySelectorAll('.job-card-container a[aria-label]')[{i}].click(); 'clicked'"
        run_cli_cmd(["browser-act", "--session", "linkedin_session", "eval", click_js])
        time.sleep(2.5) # Wait for description to load on the right
        
        # Extract title, company, description
        extract_js = f"""
        (() => {{
            const card = document.querySelectorAll('.job-card-container')[{i}];
            if (!card) return JSON.stringify({{error: 'card not found'}});
            const titleLink = card.querySelector('a[aria-label]');
            const title = titleLink ? (titleLink.getAttribute('aria-label') || titleLink.innerText) : '';
            const companyEl = card.querySelector('.pPoqHlXGWZdgNyKfaYdWCoOtQAIiVRUeWuVM') || card.querySelector('.job-card-container__company-name');
            const company = companyEl ? companyEl.innerText : '';
            const descEl = document.querySelector('#job-details');
            const description = descEl ? descEl.innerText : '';
            return JSON.stringify({{
                title: title.replace(' with verification', '').trim(),
                company: company.trim(),
                description: description.trim()
            }});
        }})()
        """
        result_str = run_cli_cmd(["browser-act", "--session", "linkedin_session", "eval", extract_js])
        
        # Parse result
        try:
            # The CLI output has some session lines first, find the JSON line
            json_line = None
            for line in result_str.split('\n'):
                line_stripped = line.strip()
                if line_stripped.startswith('{') and line_stripped.endswith('}'):
                    json_line = line_stripped
                    break
            if json_line:
                job_info = json.loads(json_line)
                if 'error' not in job_info:
                    jobs_data.append(job_info)
                    print(f"  -> Title: {job_info['title']}")
                    print(f"  -> Company: {job_info['company']}")
                else:
                    print(f"  -> Error: {job_info['error']}")
            else:
                print("  -> Error: Could not find JSON output")
        except Exception as e:
            print(f"  -> Error parsing job data: {e}")
            
    # Save to file
    output_path = "jobs_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, indent=4, ensure_ascii=False)
        
    print(f"\nSuccessfully saved {len(jobs_data)} jobs to {output_path}")
    
    # Close browser session
    print("Closing browser session...")
    run_cli_cmd(["browser-act", "session", "close", "linkedin_session"])
    browser_proc.terminate()

if __name__ == "__main__":
    main()
