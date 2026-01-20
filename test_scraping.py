import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_email_scraping():
    # Step 1: Signup
    print("\n=== SIGNUP ===")
    try:
        r = requests.post(f"{BASE_URL}/auth/signup", json={
            "email": "test@example.com",
            "password": "test123456",
            "name": "Test User"
        })
        print(f"Signup status: {r.status_code}")
        if r.status_code == 200:
            print(f"Signup OK: {r.json()}")
        elif r.status_code == 400:
            print("User may already exist, continuing...")
        else:
            print(f"Response: {r.text}")
    except Exception as e:
        print(f"Signup error: {e}")

    # Step 2: Login
    print("\n=== LOGIN ===")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@example.com",
        "password": "test123456"
    })
    print(f"Login status: {r.status_code}")
    
    if r.status_code != 200:
        print(f"Login failed: {r.text}")
        return
    
    token = r.json().get("access_token")
    print(f"Got token: {token[:50]}...")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: Search domain for emails
    print("\n=== SEARCH DOMAIN ===")
    test_domains = [
        "stripe.com",       # Large company with public emails
        "hubspot.com",      # Should have contact emails
        "zapier.com",       # Good chance of emails
    ]
    
    for domain in test_domains:
        print(f"\nTesting domain: {domain}")
        try:
            r = requests.post(
                f"{BASE_URL}/search/domain",
                json={"domain": domain},
                headers=headers,
                timeout=60
            )
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                print(f"Discovered emails: {data.get('discovered_count', 0)}")
                print(f"Personal emails: {data.get('personal_emails_found', 0)}")
                print(f"Pattern: {data.get('pattern')}")
                
                emails = data.get('emails', [])
                if emails:
                    print("Emails found:")
                    for email in emails[:5]:
                        print(f"  - {email.get('email')} ({email.get('source')})")
                else:
                    print("No emails found")
            else:
                print(f"Error: {r.text[:200]}")
        except requests.exceptions.Timeout:
            print("Request timed out")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_email_scraping()
