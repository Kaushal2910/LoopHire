import os
import json
import sys
import time
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv
from groq_client import query_groq, api_keys
from generation_helpers import slugify, save_docx_cv, save_docx_cover_letter
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables from .env file
load_dotenv()

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1MxfvJ-tJR6lZkgfv_KfbvD1F-vi7bvrmvd-3fkUtWVo")
token_path = "token.json"


def get_client_secret_path():
    # 1. Check environment variable
    env_path = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 2. Check for any client_secret_*.json in the root directory
    for f in os.listdir("."):
        if f.startswith("client_secret_") and f.endswith(".json"):
            return f
            
    # 3. Default fallback
    return "client_secret.json"


def lookup_recruiter(company_name, job_title):
    print(f"    Searching recruiter for '{job_title}' at '{company_name}'...")
    # Clean company name of trailing legal forms (Pvt Ltd, Inc, etc.) for better search
    clean_company = re.sub(r'(?i)\b(pvt|ltd|private|limited|inc|corporation|corp|gmbh|co)\b', '', company_name).strip()
    query = f'site:linkedin.com/in/ "{clean_company}" ("HR" OR "Recruiter" OR "Talent Acquisition" OR "Hiring Manager")'
    encoded_query = urllib.parse.quote(query)
    url = f"https://search.yahoo.com/search?q={encoded_query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a')
            
            recruiter_links = []
            for link in links:
                href = link.get('href', '')
                decoded_href = urllib.parse.unquote(href)
                
                # Extract clean URL if it is a Yahoo redirect
                clean_href = decoded_href
                if '/RU=' in decoded_href:
                    try:
                        clean_href = decoded_href.split('/RU=')[1].split('/RK=')[0]
                    except Exception:
                        pass
                
                # Verify it is a valid LinkedIn profile and not Yahoo's own navigation link
                if 'linkedin.com/in/' in clean_href:
                    if not any(x in clean_href for x in ['search.yahoo.com', 'news.yahoo.com', 'images.yahoo.com', 'video.yahoo.com']):
                        if clean_href not in recruiter_links:
                            recruiter_links.append(clean_href)
                            
            if recruiter_links:
                print(f"    -> Found recruiter profile: {recruiter_links[0]}")
                return recruiter_links[0]
    except Exception as e:
        print(f"      [Warning] Recruiter search failed: {e}")
        
    fallback_query = urllib.parse.quote(f'{company_name} recruiter')
    fallback_link = f"https://www.linkedin.com/search/results/people/?keywords={fallback_query}"
    print(f"    -> No specific profile found. Fallback link: {fallback_link}")
    return fallback_link

def generate_outreach_message(company_name, job_title):
    template = (
        f"Hi, I noticed the {job_title} opening at {company_name} and wanted to reach out. "
        f"With my background in software engineering, Java, Python, React, and DevOps, "
        f"I believe I could add value. I've tailored my CV for the role. "
        f"I'd love to connect and share it with you. Thanks!"
    )
    if len(template) > 300:
        template = template[:297] + "..."
    return template

# Make sure standard python re module is imported or use clean string matching
import re

def update_google_sheet(sheet_id, job_title, company_name, match_score, prep_topics, acceptance_chance, ats_score, apply_url="", recruiter_link="Pending Lookup", outreach_msg="Pending Draft", status="NOT Applied"):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    client_secret_path = get_client_secret_path()

    # Load credentials
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"  [Google Sheets API] Error loading token.json: {e}")
            
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secret_path):
                    print(f"  [Google Sheets API] Client secret file not found at '{client_secret_path}'")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"  [Google Sheets API] Authentication failed: {e}")
            return False

    # Access Google Sheets service
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_name = 'Sheet1'
        
        # Read current rows to prevent duplicates and check if headers exist
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A1:Z1000"
        ).execute()
        rows = result.get('values', [])
        
        headers = [
            "Job Title",
            "Company Name",
            "Match Score (%)",
            "Interview Prep Topics",
            "Acceptance Chance (%)",
            "Resume Ats Score (%)",
            "Application Status",
            "Application Date",
            "Job Link",
            "Recruiter Contact",
            "Outreach Message"
        ]
        
        # If sheet is empty, write headers
        if not rows:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [headers]}
            ).execute()
            print("  [Google Sheets API] Created headers in empty sheet.")
            rows = [headers]
        elif len(rows[0]) < 11:
            # Upgrade headers if columns are missing
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1:K1",
                valueInputOption="RAW",
                body={"values": [headers]}
            ).execute()
            print("  [Google Sheets API] Upgraded sheet headers to include Job Link and Outreach columns.")
            rows[0] = headers
        
        # Check for duplicates (same job title and company combination)
        for row in rows[1:]:
            if len(row) >= 2:
                existing_title = row[0].strip().lower()
                existing_company = row[1].strip().lower()
                if existing_title == job_title.strip().lower() and existing_company == company_name.strip().lower():
                    print(f"  [Google Sheets API] Duplicate entry found for '{job_title}' at '{company_name}'. Skipping.")
                    return True  # Considered successful skip

        app_date = datetime.date.today().strftime("%Y-%m-%d")
        
        new_row = [
            job_title,
            company_name,
            f"{match_score}%",
            prep_topics,
            f"{acceptance_chance}%",
            f"{ats_score}%",
            status,
            app_date,
            apply_url,
            recruiter_link,
            outreach_msg
        ]
        
        # Append new row
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [new_row]}
        ).execute()
        
        print(f"  [Google Sheets API] Successfully appended row for '{job_title}' at '{company_name}'.")
        return True
    except Exception as e:
        print(f"  [Google Sheets API] Failed to update spreadsheet: {e}")
        return False


def extract_resume_text(pdf_path):
    print(f"Extracting text from PDF: {pdf_path}...")
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        print(f"Successfully extracted {len(text)} characters of text from resume.")
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF file {pdf_path}: {e}")
        sys.exit(1)

def main():
    # 1. Verify API Keys
    if not api_keys:
        print("\n[ERROR] No Groq API keys found in your .env file.")
        print("Please add at least one Groq API key (GROQ_API_KEY) to your .env file.\n")
        sys.exit(1)

    # 2. Extract CV text
    cv_path = os.getenv("RESUME_PATH", "Kaushal_cv.pdf")
    if not os.path.exists(cv_path):
        print(f"[ERROR] Resume file '{cv_path}' not found in the workspace directory.")
        sys.exit(1)
        
    cv_text = extract_resume_text(cv_path)

    # 3. Load certificates.json
    certs_path = "certificates.json"
    certs_text = ""
    if os.path.exists(certs_path):
        try:
            with open(certs_path, "r", encoding="utf-8") as f:
                certs = json.load(f)
                certs_text = json.dumps(certs, indent=2)
            print(f"Loaded {len(certs)} certificates from {certs_path}.")
        except Exception as e:
            print(f"[Warning] Failed to load certificates.json: {e}")

    # 3b. Load projects.json
    projects_path = "projects.json"
    projects_text = ""
    if os.path.exists(projects_path):
        try:
            with open(projects_path, "r", encoding="utf-8") as f:
                projs = json.load(f)
                projects_text = json.dumps(projs, indent=2)
            print(f"Loaded {len(projs)} projects from {projects_path}.")
        except Exception as e:
            print(f"[Warning] Failed to load projects.json: {e}")

    # 3c. Load applied jobs from Google Sheet to avoid duplicates and save LLM costs
    applied_jobs = {}
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    client_secret_path = get_client_secret_path()
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"  [Google Sheets API] Error loading token.json: {e}")
            
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(client_secret_path):
                    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
        except Exception as e:
            print(f"[Warning] Google Sheets authentication failed on startup: {e}")

    if creds and creds.valid:
        try:
            service = build('sheets', 'v4', credentials=creds)
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range="'Sheet1'!A1:K1000"
            ).execute()
            rows = result.get('values', [])
            if rows and len(rows) > 1:
                for idx, row in enumerate(rows[1:], start=2):
                    if len(row) >= 2:
                        key = (row[0].strip().lower(), row[1].strip().lower())
                        applied_jobs[key] = (idx, row)
            print(f"Loaded {len(applied_jobs)} applied jobs from Google Sheets.")
        except Exception as e:
            print(f"[Warning] Failed to fetch applied jobs from Google Sheet: {e}")

    # 3d. Run scrapers automatically to fetch latest postings
    print("\n" + "=" * 60)
    print("      RUNNING JOB SCRAPERS TO FETCH LATEST POSTINGS         ")
    print("=" * 60)
    
    try:
        import scrape_advantosoftware
       " import scrape_acciojob"
        import scrape_jobs

        print("\n[*] Running LinkedIn Scraper (via browser-act)...")
        scrape_jobs.main()
        
        print("[*] Running Advanto Software Scraper...")
        scrape_advantosoftware.main()
        
        "print('\n[*] Running AccioJob Scraper...')"
       "scrape_acciojob.main()"
        
        
    except Exception as e:
        print(f"\n[Warning] Scraping phase encountered errors: {e}")
        
    print("\n" + "=" * 60)
    print("             STARTING MATCH ANALYSIS & TAILORING             ")
    print("=" * 60 + "\n")

    # 4. Read jobs data
    jobs_path = "jobs_data.json"
    if not os.path.exists(jobs_path):
        print(f"[ERROR] Job data file '{jobs_path}' not found.")
        sys.exit(1)

    with open(jobs_path, "r", encoding="utf-8") as f:
        try:
            jobs = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to parse {jobs_path}: {e}")
            sys.exit(1)

    print(f"\nLoaded {len(jobs)} jobs from {jobs_path}.\nStarting analysis...\n")
    print("=" * 70)
    print(f"{'JOB MATCH ASSESSMENT REPORT':^70}")
    print("=" * 70)

    good_matches = []

    scoring_system_prompt = """You are an expert technical recruiter evaluating candidates for software developer job opportunities.
Your task is to score the match between the candidate's CV (resume) and the job details provided, and analyze key prep and metrics.
You must rate the match on a scale of 0 to 10:
- 0 to 3: Poor match (mismatched technologies, experience level, or fields)
- 4 to 6: Average match (some overlap in skills, but significant gaps)
- 7 to 10: Good/Excellent match (great alignment of skills, technologies, and level)

Provide your assessment STRICTLY in the following JSON format:
{
  "score": <integer from 0 to 10>,
  "rationale": "<brief explanation of the score, mentioning key matching technologies or critical missing criteria>",
  "interview_prep_topics": "<a concise comma-separated list of 4-6 highly specific technical and behavioral topics critical for this specific job description, prioritizing core technologies, frameworks, and tools directly mentioned in the JD (e.g. 'React state management, Java multithreading, REST API design, CI/CD pipeline troubleshooting, DevOps principles, behavioral questions on handling project delays')>",
  "acceptance_chance": <integer probability from 0 to 100 based on match score and job requirements>,
  "resume_ats_score": <integer ATS compatibility score from 0 to 100 of the candidate's resume vs job description>
}
Do not return any other text, markdown formatting (outside of valid JSON), or explanations. Return valid JSON only."""

    generator_system_prompt = """You are an expert resume writer and career coach. Your task is to generate a tailored CV and a customized cover letter for a candidate applying to a specific job.
You must align the candidate's CV and cover letter with the job requirements and keywords, maximizing the ATS compatibility and relevance.
CRITICAL RULES:
1. Do not invent any experience, skills, projects, certifications, or achievements. No lying, only smart wording.
2. The candidate has exactly 3 work experience roles in their resume. DO NOT reduce, omit, or merge any of these 3 experience roles. Keep all 3 roles exactly, but rephrase their bullet points to emphasize relevant skills (e.g. emphasize cloud/devops for cloud roles, application development for developer roles).
3. The candidate has an Education section in their resume. You must include the Education section exactly as in the resume, preserving all details: institution, degree, expected graduation date, and coursework.
4. For Projects, you can select the 3 most relevant projects from projects.json (which contains projects like MediTrack, Sanz Cafe, NeuroBiz, and RelationOS) that match the job description. Do not reduce the projects section; always list at least 3 projects. Rephrase/tailor their bullet points to align with the job description.
5. For Certifications, select the most relevant and high-value certifications from the candidate's certificates list. Maximum 5 certifications should be present. Do not exceed 5 certifications. List them in order of relevance to the job description.
6. Do not change the layout or format of the resume. The layout must follow the original order:
   - Summary
   - Work Experience
   - Education
   - Skills
   - Certifications
   - Projects

Output your response strictly in the following JSON format:
{
  "cv": {
    "title": "<tailored job title>",
    "summary": "<tailored professional summary emphasizing matching skills>",
    "experience": [
      {
        "role": "<original role>",
        "company": "<original company>",
        "dates": "<original dates>",
        "bullets": [
          "<tailored bullet point highlighting relevance to job description>",
          "<tailored bullet point>"
        ]
      }
    ],
    "education": {
      "degree": "<original degree>",
      "institution": "<original institution>",
      "dates": "<original dates>",
      "details": "<original details/coursework>"
    },
    "skills": {
      "Programming": "<comma-separated list of programming languages the candidate knows>",
      "Web Development": "<comma-separated list of web technologies>",
      "Databases": "<comma-separated list of databases>",
      "Cloud & DevOps": "<comma-separated list of cloud/devops tools>",
      "Tools": "<comma-separated list of other tools>",
      "Core Concepts": "<comma-separated list of core concepts>"
    },
    "certifications": [
      "<relevant certification 1>",
      "<relevant certification 2>"
    ],
    "projects": [
      {
        "name": "<project name>",
        "bullets": [
          "<tailored bullet point highlighting relevant components>",
          "<tailored bullet point>"
        ]
      }
    ],
    "raw_markdown": "<A complete, beautifully formatted markdown text of the CV matching the sections order: Summary, Experience, Education, Skills, Certifications, Projects.>"
  },
  "cover_letter": {
    "body_paragraphs": [
      "<Paragraph 1: Introduction, stating interest in the specific job title and company>",
      "<Paragraph 2: Highlighting matching professional experience and skills>",
      "<Paragraph 3: Highlighting relevant projects and certifications>",
      "<Paragraph 4: Conclusion, expressing enthusiasm and call to action>"
    ],
    "raw_markdown": "<A complete, beautifully formatted markdown text of the cover letter.>"
  }
}
Ensure the output is valid JSON and nothing else."""

    for index, job in enumerate(jobs):
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        description = job.get("description", "")
        apply_url = job.get("apply_url", "")

        key = (title.strip().lower(), company.strip().lower())
        
        # 1. Update existing row in Google Sheets if missing columns
        if key in applied_jobs:
            row_idx, row_values = applied_jobs[key]
            needs_update = False
            
            # Ensure the row has at least 11 columns in memory
            while len(row_values) < 11:
                row_values.append("")
                needs_update = True
                
            # Upgrading columns if empty
            if not row_values[8] and apply_url:
                row_values[8] = apply_url
                needs_update = True
                
            if not row_values[9] or row_values[9] in ["", "Pending Lookup"] or "search/results" in row_values[9]:
                recruiter_link = lookup_recruiter(company, title)
                row_values[9] = recruiter_link
                needs_update = True
                
            if not row_values[10] or row_values[10] in ["", "Pending Draft"]:
                outreach_msg = generate_outreach_message(company, title)
                row_values[10] = outreach_msg
                needs_update = True
                
            if needs_update:
                print(f"\n[{index + 1}/{len(jobs)}] Updating existing row {row_idx} in Google Sheet for '{title}' at '{company}' with missing columns...")
                try:
                    service.spreadsheets().values().update(
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"'Sheet1'!A{row_idx}:K{row_idx}",
                        valueInputOption="USER_ENTERED",
                        body={"values": [row_values]}
                    ).execute()
                    print(f"    -> Row {row_idx} successfully updated in Sheet.")
                    applied_jobs[key] = (row_idx, row_values) # Sync memory
                except Exception as e:
                    print(f"    [Warning] Failed to update row {row_idx} in Sheet: {e}")
            else:
                print(f"\n[{index + 1}/{len(jobs)}] Skipping '{title}' at '{company}' (Already fully present in Google Sheet).")
            continue

        folder_name = slugify(company, title)
        out_dir = os.path.join("outputs", folder_name)
        gen_data_path = os.path.join(out_dir, "generation_data.json")

        # 2. Check if we already have generated files and metadata cached
        cached_data = None
        if os.path.exists(out_dir) and os.path.exists(gen_data_path):
            print(f"\n[{index + 1}/{len(jobs)}] Tailored outputs already exist for '{title}' at '{company}'. Loading cache...")
            try:
                with open(gen_data_path, "r", encoding="utf-8") as meta_f:
                    cached_data = json.load(meta_f)
            except Exception as e:
                print(f"    [Warning] Failed to read generation cache: {e}")

        score = 0
        rationale = ""
        status = "NOT Applied"
        
        if cached_data:
            match_score_pct = cached_data.get("match_score", 0)
            score = int(match_score_pct / 10)
            prep_topics = cached_data.get("interview_prep_topics", "General behavioral and technical questions")
            acceptance_chance = cached_data.get("acceptance_chance", 50)
            ats_score = cached_data.get("resume_ats_score", 50)
            status = cached_data.get("status", "Applied")
            recruiter_link = cached_data.get("recruiter_link")
            outreach_msg = cached_data.get("outreach_msg")
            
            # Auto-generate recruiter/msg if missing in cache
            if not recruiter_link or recruiter_link == "Pending Lookup":
                recruiter_link = lookup_recruiter(company, title)
                cached_data["recruiter_link"] = recruiter_link
            if not outreach_msg or outreach_msg == "Pending Draft":
                outreach_msg = generate_outreach_message(company, title)
                cached_data["outreach_msg"] = outreach_msg
                
            # Re-save updated cache
            with open(gen_data_path, "w", encoding="utf-8") as meta_f:
                json.dump(cached_data, meta_f, indent=4, ensure_ascii=False)
        else:
            scoring_user_prompt = f"""Candidate Resume Text:
{cv_text}

---
Job Details:
Title: {title}
Company: {company}
Description:
{description}"""

            print(f"\nAnalyzing job {index + 1}/{len(jobs)}: {title} at {company}...")
            
            # 1. Get Job Match Score
            result = query_groq(scoring_system_prompt, scoring_user_prompt, model="llama-3.1-8b-instant")

            if "error" in result:
                print(f"  [Error running LLM query]: {result['error']}")
                continue

            score = result.get("score", 0)
            rationale = result.get("rationale", "No rationale provided.")

            print(f"  Score: {score}/10")
            print(f"  Rationale: {rationale}")

            prep_topics = result.get("interview_prep_topics", "General behavioral and technical questions")
            acceptance_chance = result.get("acceptance_chance", score * 10)
            ats_score = result.get("resume_ats_score", score * 10)
            status = "NOT Applied"

            # 2. If Score > 6, generate tailored files
            if score <= 6:
                print(f"  [LOW MATCH] Score is {score}/10. Skipping job.")
                continue

            print(f"  >>> [MATCH DETECTED] High match score (> 6): {title} at {company} <<<")
            good_matches.append((title, company, score))
            status = "Applied"
            
            print(f"  Generating tailored documents for {title} at {company}...")
            
            generator_user_prompt = f"""Candidate Resume Text:
{cv_text}

---
Candidate Certificates JSON:
{certs_text}

---
Candidate Projects JSON:
{projects_text}

---
Job Details:
Title: {title}
Company: {company}
Description:
{description}

---
Match Score (evaluated by technical recruiter): {score}/10"""

            gen_result = query_groq(generator_system_prompt, generator_user_prompt, model="llama-3.1-8b-instant")
                
            if "error" in gen_result:
                print(f"    [Error generating documents]: {gen_result['error']}")
                continue
            else:
                try:
                    os.makedirs(out_dir, exist_ok=True)
                    
                    cv_filepath = os.path.join(out_dir, "tailored_cv.docx")
                    if not os.path.exists(cv_filepath):
                        cv_data = gen_result.get("cv", {})
                        save_docx_cv(cv_data, cv_filepath)
                        print(f"    -> Generated tailored CV saved to: {cv_filepath}")
                    
                    letter_filepath = os.path.join(out_dir, "cover_letter.docx")
                    if not os.path.exists(letter_filepath):
                        letter_data = gen_result.get("cover_letter", {})
                        save_docx_cover_letter(letter_data, letter_filepath)
                        print(f"    -> Generated Cover Letter saved to: {letter_filepath}")
                    
                    # No-op, metrics are preserved from first pass analysis
                except Exception as e:
                    print(f"    [Error writing documents to file]: {e}")

            # Search recruiter and note for new row
            recruiter_link = lookup_recruiter(company, title)
            outreach_msg = generate_outreach_message(company, title)
            match_score_pct = score * 10

            # Save cached metadata
            try:
                os.makedirs(out_dir, exist_ok=True)
                cached_metadata = {
                    "match_score": match_score_pct,
                    "interview_prep_topics": prep_topics,
                    "acceptance_chance": acceptance_chance,
                    "resume_ats_score": ats_score,
                    "recruiter_link": recruiter_link,
                    "outreach_msg": outreach_msg,
                    "status": status
                }
                with open(gen_data_path, "w", encoding="utf-8") as meta_f:
                    json.dump(cached_metadata, meta_f, indent=4, ensure_ascii=False)
                print(f"    -> Saved generation metadata cache to: {gen_data_path}")
            except Exception as cache_err:
                print(f"    [Warning] Failed to save generation metadata cache: {cache_err}")

        # Always append new row to Google Sheets
        try:
            print(f"    Updating Google Sheet for {title} at {company}...")
            match_score_pct = score * 10
            success = update_google_sheet(
                sheet_id=SPREADSHEET_ID,
                job_title=title,
                company_name=company,
                match_score=match_score_pct,
                prep_topics=prep_topics,
                acceptance_chance=acceptance_chance,
                ats_score=ats_score,
                apply_url=apply_url,
                recruiter_link=recruiter_link,
                outreach_msg=outreach_msg,
                status=status
            )
            if success:
                print(f"    [STATUS] Google Sheets update succeeded for '{title}' at '{company}'.")
                # Add to applied_jobs dict to track in-memory
                applied_jobs[key] = (len(applied_jobs) + 2, [title, company])
            else:
                print(f"    [STATUS] Google Sheets update failed for '{title}' at '{company}'.")
        except Exception as sheet_err:
            print(f"    [STATUS] Google Sheets update failed for '{title}' at '{company}': {sheet_err}")

        # Respect Groq rate limits by sleeping briefly
        time.sleep(2.0)

    print("\n" + "=" * 70)
    print(f"{'ASSESSMENT SUMMARY':^70}")
    print("=" * 70)
    
    if good_matches:
        print("\nRecommended jobs (Score > 6):")
        for idx, (title, company, score) in enumerate(good_matches):
            print(f"  {idx + 1}. {title} at {company} (Score: {score}/10)")
    else:
        print("\nNo jobs scored above 6/10.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
