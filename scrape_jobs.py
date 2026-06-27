import os
import subprocess
import time
import json
import sys
import re

def get_browser_act_cmd():
    is_windows = os.name == 'nt'
    venv_cmd = os.path.join(".venv", "Scripts", "browser-act.exe") if is_windows else os.path.join(".venv", "bin", "browser-act")
    if os.path.exists(venv_cmd):
        return venv_cmd
    return "browser-act"

def get_browser_profile_id():
    # If BROWSER_ACT_PROFILE is configured in env, use it
    env_profile = os.getenv("BROWSER_ACT_PROFILE")
    if env_profile:
        return env_profile
        
    # Otherwise, query browser-act browser list to find any configured profile
    try:
        cmd = get_browser_act_cmd()
        result = subprocess.run([cmd, "browser", "list"], capture_output=True, text=True, encoding='utf-8')
        output = result.stdout.strip()
        matches = re.findall(r'id=(\S+)', output)
        if matches:
            return matches[0]
    except Exception:
        pass
        
    # Fallback to default
    return "chrome_local_103775758939324604"

def run_cli_cmd(args):
    # Run a browser-act CLI command and return stdout
    if args and args[0] == "browser-act":
        args[0] = get_browser_act_cmd()
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    return result.stdout.strip()

def main():
    print("Starting BrowserAct Chrome session...")
    # Start the browser open process in background to keep it alive
    profile_id = get_browser_profile_id()
    browser_proc = subprocess.Popen([
        get_browser_act_cmd(), "browser", "open", profile_id,
        "https://www.linkedin.com/jobs/search/?keywords=developer&location=Pune&f_E=1",
        "--allow-restart-chrome", "--session", "linkedin_session"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for the browser and page to load
    print("\n" + "=" * 60)
    print("  ACTION REQUIRED: LINKEDIN LOG IN / SESSION VERIFICATION  ")
    print("=" * 60)
    print("  1. A Chrome browser window has been opened by browser-act.")
    print("  2. If you are not logged in to LinkedIn, please log in now.")
    print("  3. Navigate to the job search page if not loaded.")
    print("=" * 60)
    input("\n  >>> Press [ENTER] here once you are logged in and ready to scrape... ")
    print("\n[+] Continuing scraping process...\n")
    
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
            const companyEl = card.querySelector('.pPoqHlXGWZdgNyKfaYdWCoOtQAIiVRUeWuVM') || 
                              card.querySelector('.job-card-container__company-name') ||
                              card.querySelector('.artdeco-entity-lockup__subtitle') ||
                              card.querySelector('.job-card-container__primary-description') ||
                              card.querySelector('.job-card-v2__company-name');
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
            
    # Save to file, appending only new jobs
    output_path = "jobs_data.json"
    existing_jobs = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_jobs = json.load(f)
        except Exception as e:
            print(f"Error loading existing jobs data: {e}")

    existing_keys = {
        (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
        for job in existing_jobs
    }

    new_jobs_added = 0
    for job in jobs_data:
        key = (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
        if key not in existing_keys:
            existing_jobs.append(job)
            existing_keys.add(key)
            new_jobs_added += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_jobs, f, indent=4, ensure_ascii=False)
        
    print(f"\nSuccessfully added {new_jobs_added} new jobs (Total: {len(existing_jobs)}) to {output_path}")
    
    # Close browser session
    print("Closing browser session...")
    run_cli_cmd(["browser-act", "session", "close", "linkedin_session"])
    browser_proc.terminate()

if __name__ == "__main__":
    main()
