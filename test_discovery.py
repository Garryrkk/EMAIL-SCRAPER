import requests
import sys

domains = sys.argv[1:] if len(sys.argv) > 1 else ["hubspot.com", "notion.so", "stripe.com"]

for domain in domains:
    print(f"\n{'='*50}")
    print(f"Testing: {domain}")
    print('='*50)
    
    try:
        r = requests.post(
            "http://127.0.0.1:8000/api/v1/search/domain",
            json={"domain": domain},
            timeout=120
        )
        data = r.json()
        
        # New response format
        emails = data.get("emails", [])
        discovered = data.get("discovered_count", 0)
        personal = data.get("personal_emails_found", 0)
        pattern = data.get("pattern")
        
        print(f"Discovered: {discovered} work, {personal} personal")
        print(f"Pattern: {pattern}")
        print(f"Emails returned: {len(emails)}")
        
        for e in emails[:10]:
            source = e.get("source", "unknown")
            label = e.get("label", "")
            exists = e.get("exists", False)
            print(f"  - {e['email']} (source: {source}, label: {label})")
            
    except Exception as e:
        print(f"Error: {e}")

print("\nDone!")
