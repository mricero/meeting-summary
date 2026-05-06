import os
import requests
import subprocess
import time

def ensure_ollama_running():
    """Attempts to ping Ollama; if fails, starts the service."""
    try:
        # Check if service is already alive
        requests.get("http://localhost:11434/api/tags", timeout=1)
        return True
    except:
        print("[*] Ollama service not detected. Attempting to start...")
        try:
            # Start 'ollama serve' as a hidden background process
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Give it a few seconds to initialize
            time.sleep(5)
            return True
        except Exception as e:
            print(f"[-] Could not start Ollama: {e}")
            return False

def check_setup():
    # 1. Start/Check Ollama
    if not ensure_ollama_running():
        return False
    
    # 2. Check for Tectonic
    tectonic_path = os.path.join("engines", "tectonic.exe")
    if not os.path.exists(tectonic_path):
        print(f"[-] Tectonic not found at {tectonic_path}")
        return False

    # 3. Create folders
    for folder in ["vector_db", "exports"]:
        os.makedirs(folder, exist_ok=True)
    
    return True