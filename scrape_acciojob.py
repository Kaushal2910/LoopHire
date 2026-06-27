import os
import json
import time
import datetime
import subprocess
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
    if args and args[0] == "browser-act":
        args[0] = get_browser_act_cmd()
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    return result.stdout.strip()

def main():
    url = "https://placement.acciojob.com/jobs/?category=OFF_CAMPUS&filter=ALL&sourcePopup=DAILY_CURATED_JOBS"
    print(f"Launching browser-act session for Acciojob: {url}")
    
    # Open browser-act process in background
    profile_id = get_browser_profile_id()
    browser_proc = subprocess.Popen([
        get_browser_act_cmd(), "browser", "open", profile_id,
        url, "--allow-restart-chrome", "--session", "accio_session"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print("Waiting 15 seconds for dynamic content to load...")
    time.sleep(15)
    
    # JS code to batch extract jobs and intercept application link redirection
    batch_js = """
    (() => {
        return new Promise((resolve) => {
            const jobs = [];
            const rows = document.querySelectorAll('table tr');
            
            let capturedUrl = null;
            const originalOpen = window.open;
            window.open = function(url) {
                capturedUrl = url;
                return { close: () => {} };
            };

            let index = 0;
            function processNextRow() {
                if (index >= rows.length) {
                    window.open = originalOpen;
                    resolve(JSON.stringify(jobs));
                    return;
                }

                const row = rows[index];
                const cells = row.querySelectorAll('td');
                if (cells.length >= 6) {
                    const company = cells[0].innerText.trim();
                    const role = cells[1].innerText.trim();
                    
                    const skillChips = cells[2].querySelectorAll('.MuiChip-label');
                    const skills = Array.from(skillChips).map(c => c.innerText.trim()).join(', ');
                    
                    const dateAdded = cells[3].innerText.trim();
                    const source = cells[4].innerText.trim();
                    
                    const button = cells[5].querySelector('button');
                    capturedUrl = null;
                    if (button) {
                        button.click();
                    }
                    
                    setTimeout(() => {
                        const description = (
                            `Job Role: ${role}\\n` +
                            `Company: ${company}\\n` +
                            `Skills Required: ${skills}\\n` +
                            `Date Posted: ${dateAdded}\\n` +
                            `Source: Sourced from Acciojob off-campus job curation.`
                        );
                        
                        jobs.push({
                            title: role,
                            company: company,
                            skills: skills,
                            date_added: dateAdded,
                            description: description,
                            apply_url: capturedUrl || '',
                            source: "Acciojob"
                        });
                        index++;
                        processNextRow();
                    }, 100);
                } else {
                    index++;
                    processNextRow();
                }
            }
            processNextRow();
        });
    })()
    """
    
    print("Extracting job listings from dynamic table...")
    res = run_cli_cmd(["browser-act", "--session", "accio_session", "eval", batch_js])
    
    scraped_jobs = []
    
    # Extract JSON array from stdout
    json_str = None
    for line in res.split('\n'):
        line_str = line.strip()
        if line_str.startswith('[') and line_str.endswith(']'):
            json_str = line_str
            break
            
    if json_str:
        try:
            scraped_jobs = json.loads(json_str)
            print(f"Extracted {len(scraped_jobs)} job listings from Acciojob.")
        except Exception as e:
            print(f"[Error] Failed to parse JSON results: {e}")
    else:
        print("[Error] No listings returned from Acciojob DOM evaluation.")
        
    # Filter for today's jobs only to minimize token wastage
    today = datetime.date.today()
    today_str1 = f"{today.day} {today.strftime('%b')} {today.year}".lower()
    today_str2 = f"{today.strftime('%d')} {today.strftime('%b')} {today.year}".lower()
    
    print(f"Filtering jobs for today's date: '{today_str1}'")
    
    filtered_jobs = []
    for job in scraped_jobs:
        job_date = job.get("date_added", "").strip().lower()
        if job_date == today_str1 or job_date == today_str2:
            filtered_jobs.append(job)
        else:
            print(f"  -> Skipping older job: '{job['title']}' at '{job['company']}' (Posted: {job['date_added']})")
            
    # Deduplicate and append to jobs_data.json
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
    for job in filtered_jobs:
        key = (job["title"].strip().lower(), job["company"].strip().lower())
        if key not in existing_keys:
            existing_jobs.append(job)
            existing_keys.add(key)
            new_jobs_added += 1
            print(f"  -> Added new job: {job['title']} at {job['company']}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_jobs, f, indent=4, ensure_ascii=False)
        
    print(f"\n[Acciojob Scraper Complete] Added {new_jobs_added} new jobs. Total jobs in list: {len(existing_jobs)}")
    
    # Close browser session
    print("Closing browser session...")
    run_cli_cmd(["browser-act", "session", "close", "accio_session"])
    browser_proc.terminate()

if __name__ == '__main__':
    main()
