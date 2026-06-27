#!/usr/bin/env python
import os
import sys
import subprocess
import shutil

def check_command(cmd):
    """Checks if a command-line tool is available."""
    return shutil.which(cmd) is not None

def print_banner():
    print("=" * 60)
    print("                AI JOBS SETUP & INSTALLATION                ")
    print("=" * 60)

def main():
    print_banner()

    # Determine paths based on OS
    is_windows = os.name == 'nt'
    venv_dir = ".venv"
    
    if is_windows:
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        activate_cmd = f"{venv_dir}\\Scripts\\activate"
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        activate_cmd = f"source {venv_dir}/bin/activate"

    # 1. Create virtual environment if it doesn't exist
    if not os.path.exists(venv_dir):
        print(f"[*] Virtual environment ({venv_dir}) not found. Creating it...")
        # Check if uv is available for much faster environment creation
        if check_command("uv"):
            print("    -> Found 'uv'. Creating venv using uv...")
            subprocess.run(["uv", "venv", venv_dir], check=True)
        else:
            print("    -> Creating venv using standard 'venv' module...")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        print("[+] Virtual environment created successfully.")
    else:
        print("[+] Virtual environment already exists.")

    # 2. Install dependencies
    if not os.path.exists("requirements.txt"):
        print("[!] requirements.txt not found. Cannot install Python packages.")
    else:
        print("[*] Installing/upgrading dependencies in the virtual environment...")
        if check_command("uv"):
            print("    -> Found 'uv'. Installing dependencies via uv...")
            # Use uv pip install with the venv python
            subprocess.run(["uv", "pip", "install", "-r", "requirements.txt", "--python", venv_python], check=True)
        else:
            print("    -> Installing dependencies via standard pip...")
            subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
            subprocess.run([venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("[+] Dependencies installed successfully.")

    # 3. Create .env if it doesn't exist
    if not os.path.exists(".env"):
        print("[*] Creating .env file from .env.example...")
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
            print("[+] Created .env file.")
        else:
            with open(".env", "w") as f:
                f.write("GROQ_ACCOUNT_1=\nRESUME_PATH=Resume.pdf\nSPREADSHEET_ID=1MxfvJ-tJR6lZkgfv_KfbvD1F-vi7bvrmvd-3fkUtWVo\n")
            print("[+] Created blank .env file.")
        
        # Interactive configuration helper
        print("\n--- Configuration Assistant ---")
        groq_key = input("Enter your Groq API Key (leave empty to configure manually later): ").strip()
        if groq_key:
            with open(".env", "r") as f:
                lines = f.readlines()
            with open(".env", "w") as f:
                for line in lines:
                    if line.startswith("GROQ_ACCOUNT_1="):
                        f.write(f"GROQ_ACCOUNT_1={groq_key}\n")
                    elif line.startswith("GROQ_API_KEY="):
                        f.write(f"GROQ_ACCOUNT_1={groq_key}\n")
                    else:
                        f.write(line)
            print("[+] Groq API Key saved to .env file.")
    else:
        print("[+] .env file already exists. Skipping environment copy.")

    # 4. Copy projects and certificates example files if they don't exist
    if not os.path.exists("projects.json"):
        if os.path.exists("projects.json.example"):
            shutil.copy("projects.json.example", "projects.json")
            print("[+] Created projects.json from projects.json.example")
        else:
            with open("projects.json", "w") as f:
                f.write("[]\n")
            print("[+] Created empty projects.json")
    else:
        print("[+] projects.json already exists.")

    if not os.path.exists("certificates.json"):
        if os.path.exists("certificates.json.example"):
            shutil.copy("certificates.json.example", "certificates.json")
            print("[+] Created certificates.json from certificates.json.example")
        else:
            with open("certificates.json", "w") as f:
                f.write("[]\n")
            print("[+] Created empty certificates.json")
    else:
        print("[+] certificates.json already exists.")

    # 5. Check if browser-act is installed and auto-create profile if missing
    venv_browser_act = os.path.join(venv_dir, "Scripts", "browser-act.exe") if is_windows else os.path.join(venv_dir, "bin", "browser-act")
    browser_act_installed = check_command("browser-act") or os.path.exists(venv_browser_act)
    
    if not browser_act_installed:
        print("[*] 'browser-act' is required for LinkedIn/Acciojob scraping but was not found.")
        print("[*] Installing browser-act-cli inside the virtual environment...")
        try:
            if check_command("uv"):
                subprocess.run(["uv", "pip", "install", "browser-act-cli", "--python", venv_python], check=True)
            else:
                subprocess.run([venv_python, "-m", "pip", "install", "browser-act-cli"], check=True)
            browser_act_installed = True
            print("[+] Successfully installed browser-act-cli.")
        except Exception as e:
            print(f"[Warning] Failed to automatically install browser-act-cli: {e}")

    if browser_act_installed:
        browser_act_bin = venv_browser_act if os.path.exists(venv_browser_act) else "browser-act"
        try:
            res = subprocess.run([browser_act_bin, "browser", "list"], capture_output=True, text=True)
            if not res.stdout.strip():
                print("[*] No browser-act profiles found. Creating default 'scrape' browser...")
                subprocess.run([
                    browser_act_bin, "browser", "create", 
                    "--type", "chrome", 
                    "--name", "scrape", 
                    "--desc", "Default browser for scraping"
                ], check=True)
                print("[+] Default browser-act profile created successfully.")
            else:
                print("[+] Found existing browser-act profiles.")
        except Exception as e:
            print(f"[Warning] Failed to verify/create browser-act profile: {e}")



    # 6. Success Banner and Next Steps
    print("\n" + "=" * 60)
    print("                    SETUP COMPLETED SUCCESSFULLY!           ")
    print("=" * 60)
    print("\nNext Steps to run the application:")
    print(f"  1. Activate the virtual environment:")
    print(f"     Command: {activate_cmd}")
    print(f"  2. Add your resume PDF file and match its name in '.env' (RESUME_PATH=...)")
    print(f"  3. Populate your details in 'projects.json' and 'certificates.json'")
    
    if not browser_act_installed:
        print(f"  4. [Required for LinkedIn/Acciojob Scraping] Install browser-act:")
        print(f"     Run: pip install browser-act-cli")
        print(f"     Or:  uv tool install browser-act-cli --python 3.12")
        print(f"  5. Run the application (scrapes, analyzes, and tailors in one step):")
        print(f"     Command: python main.py")
    else:
        print(f"  4. Run the application (scrapes, analyzes, and tailors in one step):")
        print(f"     Command: python main.py")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
