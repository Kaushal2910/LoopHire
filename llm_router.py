import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

class LLMRouter:
    def __init__(self):
        self.providers = {
            "groq": self._load_accounts("GROQ_ACCOUNT_"),
            "nvidia": self._load_accounts("NVIDIA_ACCOUNT_"),
            "gemini": self._load_accounts("GEMINI_ACCOUNT_")
        }
        
        # Keep track of active indices per provider
        # provider -> [account_idx, key_idx]
        self.indices = {
            "groq": [0, 0],
            "nvidia": [0, 0],
            "gemini": [0, 0]
        }
        
        # Keep track of account cooldowns
        # (provider, account_name) -> timestamp when cooldown ends
        self.cooldowns = {}
        
        # Print status of loaded keys on initialization
        for prov, accs in self.providers.items():
            tot_keys = sum(len(k) for k in accs.values())
            print(f"Loaded {len(accs)} accounts ({tot_keys} keys) for provider '{prov}'.")

    def _load_accounts(self, prefix):
        # Scan environment variables for accounts matching prefix
        accounts = {}
        for key, val in os.environ.items():
            if key.startswith(prefix) and val.strip():
                account_name = key
                keys = [k.strip() for k in val.split(",") if k.strip()]
                if keys:
                    accounts[account_name] = keys
        
        # Sort accounts to maintain consistent ordering
        sorted_account_names = sorted(accounts.keys())
        return {name: accounts[name] for name in sorted_account_names}

    def _get_next_key(self, provider):
        accounts = self.providers.get(provider, {})
        if not accounts:
            return None, None, None

        account_names = list(accounts.keys())
        num_accounts = len(account_names)
        
        # Find next available account (not on cooldown)
        current_time = time.time()
        
        for _ in range(num_accounts):
            account_idx = self.indices[provider][0] % num_accounts
            account_name = account_names[account_idx]
            
            # Rotate account index for next request (round-robin)
            self.indices[provider][0] += 1
            
            # Check cooldown
            cooldown_until = self.cooldowns.get((provider, account_name), 0)
            if current_time < cooldown_until:
                # This account is on cooldown, skip it
                continue
                
            keys = accounts[account_name]
            key_idx = self.indices[provider][1] % len(keys)
            
            # Rotate key index within this account for the next time it's used
            self.indices[provider][1] += 1
            
            active_key = keys[key_idx]
            return active_key, account_name, account_idx
            
        # If all accounts are on cooldown, pick the first one and force it (or sleep)
        first_account = account_names[0]
        cooldown_until = self.cooldowns.get((provider, first_account), 0)
        wait_time = max(0.1, cooldown_until - current_time)
        if wait_time > 0 and wait_time < 30:
            print(f"  [Router] All {provider} accounts on cooldown. Waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
            
        # Reset cooldown and return
        self.cooldowns[(provider, first_account)] = 0
        keys = accounts[first_account]
        return keys[0], first_account, 0

    def set_cooldown(self, provider, account_name, duration=15):
        print(f"  [Router] Account '{account_name}' ({provider}) hit rate limit. Cooldown set for {duration}s.")
        self.cooldowns[(provider, account_name)] = time.time() + duration

    def query(self, provider, system_prompt, user_prompt, model, json_output=True, temperature=0.1, max_retries=10):
        # Determine URL based on provider
        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
        elif provider == "nvidia":
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
        elif provider == "gemini":
            url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        else:
            raise ValueError(f"Unknown provider: {provider}")

        for attempt in range(max_retries):
            key, account_name, account_idx = self._get_next_key(provider)
            if not key:
                return {"error": f"No API keys configured for provider '{provider}'"}

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature
            }
            
            if json_output:
                data["response_format"] = {"type": "json_object"}

            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                # Check for rate limit (429)
                if response.status_code == 429:
                    self.set_cooldown(provider, account_name, duration=15)
                    continue
                    
                # Check for auth errors (401/403)
                if response.status_code in [401, 403]:
                    print(f"  [Router] Auth error (code {response.status_code}) on {provider} account '{account_name}'. Rotating...")
                    self.set_cooldown(provider, account_name, duration=300) # Long cooldown for bad keys
                    continue

                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                if json_output:
                    return json.loads(content)
                return content
            except Exception as e:
                print(f"  [Router] Error querying {provider} (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(1)

        return {"error": f"Failed after {max_retries} retries for provider '{provider}'"}

# Default shared router instance
router = LLMRouter()
