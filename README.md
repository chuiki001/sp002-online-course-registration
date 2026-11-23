# SP-002: Online Course Registration Portal

**Student:** Chika Praise Palngnen (`U23CS1038`)  
**Course:** Personal Software Engineering Project (13-Week Capstone)  
**Tech Stack:** Python 3.11 • FastAPI • SQLAlchemy • PostgreSQL / SQLite • Tailwind CSS

## Quick Start (Zero-Config Local Run)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000` in your browser for the interactive portal UI, or `http://127.0.0.1:8000/docs` for the Swagger API documentation.

### Demo Credentials (Pre-seeded on Startup)
- **Student:** `u23cs1038@afit.edu.ng` / `student123`
- **Advisor:** `advisor@afit.edu.ng` / `advisor123`
- **Admin:** `admin@afit.edu.ng` / `admin123`

## Running Automated Tests & Coverage (Week 10)
```bash
pytest --cov=app --cov-report=term-missing
```
