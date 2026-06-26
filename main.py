import os
import json
import sys
from pypdf import PdfReader
from dotenv import load_dotenv
from groq_client import query_groq

# Load environment variables from .env file
load_dotenv()

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
    # 1. Verify Groq API Key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[ERROR] GROQ_API_KEY is not set.")
        print("Please create a '.env' file in this directory and add your key:")
        print("GROQ_API_KEY=your_actual_groq_api_key_here\n")
        sys.exit(1)

    # 2. Extract CV text
    cv_path = "Resume_Kaushal.pdf"
    if not os.path.exists(cv_path):
        print(f"[ERROR] Resume file '{cv_path}' not found in the workspace directory.")
        sys.exit(1)
        
    cv_text = extract_resume_text(cv_path)

    # 3. Read jobs data
    jobs_path = "jobs_data.json"
    if not os.path.exists(jobs_path):
        print(f"[ERROR] Job data file '{jobs_path}' not found. Please run scrape_jobs.py first.")
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

    system_prompt = """You are an expert technical recruiter evaluating candidates for software developer job opportunities.
Your task is to score the match between the candidate's CV (resume) and the job details provided.
You must rate the match on a scale of 0 to 10:
- 0 to 3: Poor match (mismatched technologies, experience level, or fields)
- 4 to 6: Average match (some overlap in skills, but significant gaps)
- 7 to 10: Good/Excellent match (great alignment of skills, technologies, and level)

Provide your assessment STRICTLY in the following JSON format:
{
  "score": <integer from 0 to 10>,
  "rationale": "<brief explanation of the score, mentioning key matching technologies or critical missing criteria>"
}
Do not return any other text, markdown formatting (outside of valid JSON), or explanations. Return valid JSON only."""

    for index, job in enumerate(jobs):
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        description = job.get("description", "")

        user_prompt = f"""Candidate Resume Text:
{cv_text}

---
Job Details:
Title: {title}
Company: {company}
Description:
{description}"""

        print(f"\nAnalyzing job {index + 1}/{len(jobs)}: {title} at {company}...")
        
        # Query Groq
        result = query_groq(system_prompt, user_prompt)

        if "error" in result:
            print(f"  [Error running LLM query]: {result['error']}")
            continue

        score = result.get("score", 0)
        rationale = result.get("rationale", "No rationale provided.")

        print(f"  Score: {score}/10")
        print(f"  Rationale: {rationale}")

        if score > 6:
            print(f"  >>> [MATCH DETECTED] High match score (> 6): {title} at {company} <<<")
            good_matches.append((title, company, score))

        # Respect Groq rate limits by sleeping briefly
        import time
        time.sleep(1.5)

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
