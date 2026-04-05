import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print(f"--- Direct API Test with curl ---")
print(f"API Key starts with: {api_key[:4] if api_key else 'None'}")

# Use gemini-1.5-flash
curl_command = f'curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}" ' \
               f'-H "Content-Type: application/json" ' \
               f'-d "{{\\"contents\\": [{{\\"parts\\":[{{\\"text\\": \\"Hello!\\"}}]}}]}}"'

try:
    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
except Exception as e:
    print(f"Error: {e}")
