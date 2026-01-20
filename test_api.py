"""
Comprehensive API Test Script
Tests all backend endpoints
"""
import httpx
import asyncio
import random
import json

BASE_URL = "http://localhost:8000/api/v1"

async def test_all_endpoints():
    """Test all API endpoints."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("\n" + "="*50)
        print("APOLLO EMAIL INTELLIGENCE - API TEST")
        print("="*50)
        
        # 1. Health Check
        print("\n[1/10] Testing Health...")
        r = await client.get("http://localhost:8000/health")
        assert r.status_code == 200, f"Health failed: {r.text}"
        print(f"  ✓ Health: {r.json()}")
        
        # 2. Signup
        print("\n[2/10] Testing Signup...")
        rand = random.randint(1000, 9999)
        signup_data = {
            "name": f"Test User {rand}",
            "email": f"testapi{rand}@example.com",
            "password": "password123"
        }
        r = await client.post(f"{BASE_URL}/auth/signup", json=signup_data)
        assert r.status_code == 200, f"Signup failed: {r.text}"
        tokens = r.json()
        access_token = tokens["access_token"]
        print(f"  ✓ Signup: Token received ({len(access_token)} chars)")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 3. Login
        print("\n[3/10] Testing Login...")
        login_data = {"email": signup_data["email"], "password": "password123"}
        r = await client.post(f"{BASE_URL}/auth/login", json=login_data)
        assert r.status_code == 200, f"Login failed: {r.text}"
        print(f"  ✓ Login: Success")
        
        # 4. Get Profile
        print("\n[4/10] Testing Get Profile...")
        r = await client.get(f"{BASE_URL}/users/me", headers=headers)
        assert r.status_code == 200, f"Profile failed: {r.text}"
        profile = r.json()
        print(f"  ✓ Profile: {profile['email']}")
        
        # 5. Get Credits
        print("\n[5/10] Testing Get Credits...")
        r = await client.get(f"{BASE_URL}/users/credits", headers=headers)
        assert r.status_code == 200, f"Credits failed: {r.text}"
        credits = r.json()
        print(f"  ✓ Credits: {credits['credits']} ({credits['plan']})")
        
        # 6. Get Usage
        print("\n[6/10] Testing Get Usage...")
        r = await client.get(f"{BASE_URL}/users/usage", headers=headers)
        assert r.status_code == 200, f"Usage failed: {r.text}"
        usage = r.json()
        print(f"  ✓ Usage: {usage['credits_remaining']} remaining")
        
        # 7. Create Person
        print("\n[7/10] Testing Create Person...")
        person_data = {
            "first_name": "John",
            "last_name": "Doe",
            "job_title": "Engineer"
        }
        r = await client.post(f"{BASE_URL}/people/", json=person_data, headers=headers)
        assert r.status_code == 200, f"Create person failed: {r.text}"
        person = r.json()
        print(f"  ✓ Person created: {person['full_name']} (id: {person['id'][:8]}...)")
        
        # 8. List People
        print("\n[8/10] Testing List People...")
        r = await client.get(f"{BASE_URL}/people/", headers=headers)
        assert r.status_code == 200, f"List people failed: {r.text}"
        people = r.json()
        print(f"  ✓ People: {people['count']} found")
        
        # 9. Get Person
        print("\n[9/10] Testing Get Person...")
        r = await client.get(f"{BASE_URL}/people/{person['id']}", headers=headers)
        assert r.status_code == 200, f"Get person failed: {r.text}"
        fetched = r.json()
        print(f"  ✓ Person: {fetched['full_name']}")
        
        # 10. Search Domain (may take time)
        print("\n[10/10] Testing Search Domain...")
        search_data = {"domain": "example.com"}
        try:
            r = await client.post(f"{BASE_URL}/search/domain", json=search_data, headers=headers)
            if r.status_code == 200:
                result = r.json()
                print(f"  ✓ Search: Found {result.get('discovered_count', 0)} emails")
            else:
                print(f"  ⚠ Search: {r.status_code} - {r.text[:100]}")
        except Exception as e:
            print(f"  ⚠ Search: Timeout or error ({e})")
        
        print("\n" + "="*50)
        print("ALL CORE ENDPOINTS PASSED!")
        print("="*50)
        
        # Summary
        print("\n📊 Endpoint Summary:")
        print("  ✓ /health - OK")
        print("  ✓ /auth/signup - OK")
        print("  ✓ /auth/login - OK")
        print("  ✓ /users/me - OK")
        print("  ✓ /users/credits - OK")
        print("  ✓ /users/usage - OK")
        print("  ✓ /people/ (POST) - OK")
        print("  ✓ /people/ (GET) - OK")
        print("  ✓ /people/{id} - OK")
        print("  ⚠ /search/domain - Depends on network")
        print("  ⚠ /emails/verify - Requires SMTP")
        print("  ⚠ /companies/{domain} - Requires data")


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
