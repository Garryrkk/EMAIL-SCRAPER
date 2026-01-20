@echo off
cd /d "c:\Users\Crazy\Documents\CODES\EMAIL-SCAPPER\EMAIL-SCRAPER\backend"
start /B python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
timeout /t 10 /nobreak
cd /d "c:\Users\Crazy\Documents\CODES\EMAIL-SCAPPER\EMAIL-SCRAPER"
python test_discovery.py %*
