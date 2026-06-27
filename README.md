# AI Jobs Matcher & Resume Tailor

An automated assistant that scrapes developer job postings, scores match quality against your resume, and generates tailored CVs (as Word `.docx` documents) and cover letters for high-scoring matches. The results are also tracked in a Google Sheets spreadsheet.

---

## Features

- **Automated Scraping**: Pulls job listings from platforms (e.g. Advanto Software, AccioJob).
- **Match Analysis**: Scores match compatibility using an LLM model and rates readiness.
- **Auto-Tailored Outputs**: Generates customized resumes and cover letters in Microsoft Word format under the `outputs/` folder.
- **Spreadsheet Tracking**: Synchronizes analysis results directly to a Google Sheets document, including recruiter LinkedIn profiles and custom outreach drafts.

---

## Quick Setup

To make setting up the project on any new machine as easy as possible, we have provided a cross-platform setup utility.

### Prerequisite
Ensure you have **Python 3.8+** installed on your system.
login to you linkedin Account

### Steps
1. **Pull the Repository**:
   ```bash
   git clone <repository-url>
   cd AI_jobs
   ```

2. **Run the Setup Script**:
   - **Windows**: Double-click `setup.bat` or run:
     ```powershell
     .\setup.bat
     ```
   - **macOS / Linux**: Run:
     ```bash
     chmod +x setup.sh
     ./setup.sh
     ```

   *The script will automatically create a Python virtual environment, install all dependencies, create your `.env` configuration file, and automatically generate your `projects.json` and `certificates.json` files.*

3. **Configure your Details**:
   - Open `.env` and fill in your LLM API Keys (Groq, Gemini, or Nvidia).
   - Set the `RESUME_PATH` in `.env` to point to your resume PDF file (or place your resume in the root folder as `Resume.pdf`).
   - Open and populate the newly generated [projects.json] and [certificates.json] with your own experience details (refer to the `.example` files for reference).

### Google Sheets API Setup 
To log results to a Google Sheet automatically:
1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a project, and search enable the **Google Sheets API** and **Google drive API**.
2. Go to **Credentials**, click **Create Credentials** -> **OAuth Client ID** (select **Desktop Application**), and download the client secrets JSON. 
3. Rename the downloaded file to `client_secret.json` and place it in the root folder of this project.
4. Then in same Project go to **Api and Services** --> **OAuth consent screen** then go to **Audience** then scroll down to test user add your email id there.
5. Open Spreadsheet in chrome and copy the ID . add that to "SPREADSHEET_ID" in **.env**
6. On your first run, a browser window will open to authenticate and link your account (creating `token.json` automatically).


---

## How to Run

1. **Activate the Virtual Environment**:
   - **Windows**:
     ```powershell
     .venv\Scripts\activate
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

2. **Scrape Job Openings**:
   Run the scraping script to fetch the latest job listings:
   ```bash
   python scrape_jobs.py
   ```

3. **Run Match Analysis & Tailoring**:
   Run the main analysis script:
   ```bash
   python main.py
   ```

All generated files (tailored resumes and cover letters) will be created inside the `outputs/` folder, organized by company and job title.
