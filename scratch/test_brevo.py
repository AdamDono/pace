import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

brevo_key = os.getenv('BREVO_API_KEY')
print(f"Brevo API Key from .env: {brevo_key[:20] if brevo_key else 'None'}...")

url = "https://api.brevo.com/v3/smtp/email"
headers = {
    "api-key": brevo_key,
    "Content-Type": "application/json"
}

payload = {
    "sender": {"email": "flipbrickzmusic1@gmail.com", "name": "Pace Academy Test"},
    "to": [{"email": "adamdono100@gmail.com"}],
    "subject": "Brevo API Test",
    "htmlContent": "<h3>Hello from Pace Academy Brevo test!</h3>"
}

try:
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'), 
        headers=headers, 
        method='POST'
    )
    with urllib.request.urlopen(req) as response:
        print(f"Response Status: {response.status}")
        print(f"Response Body: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Error occurred: {e}")
