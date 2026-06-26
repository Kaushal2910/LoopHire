import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def query_groq(system_prompt, user_prompt, model="llama-3.3-70b-versatile"):
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set. Please set it in your environment or in a .env file.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    import time
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
            if response.status_code == 429:
                # Rate limit hit, wait and retry
                retry_after = 9  # Default wait time
                try:
                    # Try to extract the wait time from headers or error message
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", "")
                    if "in " in err_msg and "s." in err_msg:
                        # Extract e.g. "8.815" from "Please try again in 8.815s."
                        parts = err_msg.split("in ")
                        if len(parts) > 1:
                            sec_part = parts[1].split("s.")[0].strip()
                            retry_after = float(sec_part)
                except Exception:
                    pass
                
                print(f"  [Rate Limit Hit] Waiting {retry_after + 1}s before retrying (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_after + 1)
                continue
                
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 401:
                return {"error": "Unauthorized. Please check your GROQ_API_KEY."}
            return {"error": f"HTTP error occurred: {http_err}. Response: {response.text}"}
        except Exception as err:
            return {"error": f"An error occurred: {err}"}
    return {"error": "Failed after maximum retries due to rate limiting."}

if __name__ == "__main__":
    # Quick self-test if run directly
    if not GROQ_API_KEY:
        print("Error: GROQ_API_KEY environment variable is not configured.")
        print("Create a '.env' file in this directory and add: GROQ_API_KEY=your_key_here")
    else:
        print("Groq Client initialized. API Key configured successfully.")
