@echo off
cd /d "c:\Users\Crazy\Documents\CODES\EMAIL-SCAPPER\EMAIL-SCRAPER\backend"
set PYTHONPATH=.
python -c "from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000)"
