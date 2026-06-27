import os
import json
from llm_router import router

# Backward compatibility: collect all loaded Groq keys
api_keys = []
for acc_name, keys in router.providers.get("groq", {}).items():
    api_keys.extend(keys)

# If no account keys were found in the new format, check old GROQ_API_KEY env for safety
if not api_keys:
    groq_env_key = os.getenv("GROQ_API_KEY")
    if groq_env_key:
        api_keys.extend([k.strip() for k in groq_env_key.split(",") if k.strip()])
    for i in range(1, 11):
        key = os.getenv(f"GROQ_API_KEY_{i}")
        if key and key.strip() not in api_keys:
            api_keys.append(key.strip())
            
    # Load into router structure as a default fallback account
    if api_keys:
        router.providers["groq"]["GROQ_ACCOUNT_DEFAULT"] = api_keys

def query_groq(system_prompt, user_prompt, model="llama-3.1-8b-instant"):
    """
    Backward-compatible wrapper function for Groq API calls.
    Routes queries through the advanced multi-account router.
    """
    return router.query(
        provider="groq",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        json_output=True
    )

if __name__ == "__main__":
    print(f"Backward-compatible Groq client loaded with {len(api_keys)} keys across all accounts.")
