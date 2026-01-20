#!/usr/bin/env python
"""Test script for email scraper"""
import requests
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"

def get_token():
    """Login or register and get token"""
    login_resp = requests.post(f'{BASE_URL}/auth/login', json={
        'email': 'test@test.com',
        'password': 'password123'
    })
    
    if login_resp.status_code != 200:
        print("Login failed, trying signup...")
        reg_resp = requests.post(f'{BASE_URL}/auth/signup', json={
            'email': 'test@test.com',
            'password': 'password123',
            'name': 'Test User'
        })
        print(f"Signup: {reg_resp.status_code}")
        
        login_resp = requests.post(f'{BASE_URL}/auth/login', json={
            'email': 'test@test.com',
            'password': 'password123'
        })
    
    if login_resp.status_code == 200:
        return login_resp.json().get('access_token')
    else:
        print(f"Login failed: {login_resp.status_code}")
        print(f"Response: {login_resp.text}")
        return None


def test_domain(token, domain):
    """Test email discovery on a domain"""
    print(f"\n{'='*50}")
    print(f"Testing: {domain}")
    print('='*50)
    
    try:
        search_resp = requests.post(f'{BASE_URL}/search/domain',
            headers={'Authorization': f'Bearer {token}'},
            json={'domain': domain},
            timeout=180
        )
        
        print(f"Status: {search_resp.status_code}")
        
        if search_resp.status_code == 200:
            data = search_resp.json()
            
            # Get all emails
            all_emails = data.get('emails', [])
            
            # Separate by type
            work = [e for e in all_emails if e.get('email_type') == 'work']
            personal = [e for e in all_emails if e.get('email_type') == 'personal']
            
            # Also check for work_emails/personal_emails keys (alternate format)
            if not all_emails:
                work = data.get('work_emails', [])
                personal = data.get('personal_emails', [])
            
            print(f"\nWork Emails Found: {len(work)}")
            for e in work[:10]:
                email_addr = e.get('email', e.get('address', str(e)))
                conf = e.get('deliverability_confidence', e.get('confidence', 0))
                if isinstance(conf, float):
                    conf = int(conf * 100)
                print(f"  ✓ {email_addr} (confidence: {conf}%)")
            
            print(f"\nPersonal Emails Found: {len(personal)}")
            for e in personal[:5]:
                email_addr = e.get('email', e.get('address', str(e)))
                print(f"  • {email_addr}")
            
            # Print stats
            stats = data.get('stats', {})
            if stats:
                print(f"\nStats: {stats}")
            
            return len(work), len(personal)
        else:
            print(f"Error: {search_resp.text[:500]}")
            return 0, 0
            
    except requests.exceptions.Timeout:
        print("Timeout - request took too long")
        return 0, 0
    except Exception as e:
        print(f"Exception: {e}")
        return 0, 0


def main():
    domains = sys.argv[1:] if len(sys.argv) > 1 else ['stripe.com']
    
    print("Email Scraper Test")
    print("="*50)
    
    token = get_token()
    if not token:
        print("Failed to get auth token")
        return
    
    print(f"Got auth token: {token[:20]}...")
    
    total_work = 0
    total_personal = 0
    
    for domain in domains:
        work, personal = test_domain(token, domain)
        total_work += work
        total_personal += personal
    
    print(f"\n{'='*50}")
    print(f"TOTAL: {total_work} work emails, {total_personal} personal emails")
    print('='*50)


if __name__ == '__main__':
    main()
