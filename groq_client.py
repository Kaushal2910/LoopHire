import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Support multiple Groq API keys: comma-separated or numbered env variables
api_keys = []
groq_env_key = os.getenv("GROQ_API_KEY")
if groq_env_key:
    api_keys.extend([k.strip() for k in groq_env_key.split(",") if k.strip()])

for i in range(1, 11):
    key = os.getenv(f"GROQ_API_KEY_{i}")
    if key and key.strip() not in api_keys:
        api_keys.append(key.strip())

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
current_key_idx = 0

def query_groq(system_prompt, user_prompt, model="llama-3.1-8b-instant"):
    global current_key_idx
    if not api_keys:
        raise ValueError("GROQ_API_KEY is not set. Please set it in your environment or in a .env file.")

    import time
    
    # Try up to twice the number of keys to ensure rotation handles temporary rate limits
    max_attempts = max(3, len(api_keys) * 2)
    
    for attempt in range(max_attempts):
        active_key = api_keys[current_key_idx % len(api_keys)]
        headers = {
            "Authorization": f"Bearer {active_key}",
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

        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
            if response.status_code == 429:
                print(f"  [Rate Limit on Groq Key #{current_key_idx % len(api_keys) + 1}] Rotating keys...")
                current_key_idx += 1
                
                retry_after = 5  # Default wait time
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", "")
                    if "in " in err_msg and "s." in err_msg:
                        sec_part = err_msg.split("in ")[1].split("s.")[0].strip()
                        retry_after = float(sec_part)
                except Exception:
                    pass
                print(f"  Rate limit hit. Waiting {retry_after + 1}s before retrying...")
                time.sleep(retry_after + 1)
                continue
                
            if response.status_code == 401 or response.status_code == 403:
                print(f"  [Auth Error on Groq Key #{current_key_idx % len(api_keys) + 1}] Rotating key and retrying...")
                current_key_idx += 1
                time.sleep(0.5)
                continue
                
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"HTTP error occurred: {http_err}. Response: {response.text}"}
        except Exception as err:
            return {"error": f"An error occurred: {err}"}
            
    return {"error": "Failed after maximum retries due to rate limiting or authentication issues."}

if __name__ == "__main__":
    print(f"Groq client loaded with {len(api_keys)} keys.")
