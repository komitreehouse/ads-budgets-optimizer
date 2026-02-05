# Setup Instructions

## Quick Start

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

This will install all required packages including:
- FastAPI and uvicorn (for the API server)
- Streamlit (for the frontend)
- SQLAlchemy, APScheduler, Flask (for backend services)
- All other dependencies

### 2. Initialize Database

```bash
python3 -c "from src.bandit_ads.database import init_database; init_database(create_tables=True)"
```

### 3. Test the API

```bash
python3 scripts/test_api.py
```

### 4. Start the API Server

```bash
python3 scripts/run_api.py
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### 5. Start the Frontend

In a new terminal:

```bash
streamlit run frontend/app.py
```

The frontend will automatically connect to the API if it's running.

## Troubleshooting

### FastAPI not found

If you see `ModuleNotFoundError: No module named 'fastapi'`:
```bash
pip3 install fastapi uvicorn[standard] python-multipart
```

### Database errors

Make sure the database is initialized:
```bash
python3 -c "from src.bandit_ads.database import init_database; init_database(create_tables=True)"
```

### Port already in use

If port 8000 is already in use, use a different port:
```bash
python3 scripts/run_api.py --port 8001
```

Then set the environment variable:
```bash
export API_BASE_URL=http://localhost:8001
```

## Development Workflow

1. **Terminal 1**: Run API server
   ```bash
   python3 scripts/run_api.py --reload
   ```

2. **Terminal 2**: Run frontend
   ```bash
   streamlit run frontend/app.py
   ```

3. **Terminal 3**: Run tests (optional)
   ```bash
   python3 scripts/test_api.py
   ```

## Next Steps

After setup:
1. Test API endpoints at `http://localhost:8000/docs`
2. Verify frontend connects to API
3. Add sample data to database for testing
4. Complete frontend pages as needed
