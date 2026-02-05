# Quick Start Guide

## Prerequisites

✅ FastAPI is installed in your virtual environment (`.venv`)

## Step 1: Activate Virtual Environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your terminal prompt.

## Step 2: Create Sample Data (Optional but Recommended)

```bash
python scripts/create_sample_data.py
```

This creates:
- 5 sample campaigns
- 15-25 arms
- 30 days of metrics

**Note:** If you get a database schema error, run the migration first:
```bash
python scripts/migrate_database.py
```

## Step 3: Start the API Server

```bash
python scripts/run_api.py
```

**Or with auto-reload for development:**
```bash
python scripts/run_api.py --reload
```

The API will start on `http://localhost:8000`

You should see:
```
Starting Ads Budget Optimizer API on http://0.0.0.0:8000
API docs available at http://0.0.0.0:8000/docs
```

## Step 4: Test the API

In a new terminal (keep API running), test the endpoints:

```bash
# Activate venv
source .venv/bin/activate

# Health check
curl http://localhost:8000/api/health

# Get campaigns
curl http://localhost:8000/api/campaigns

# Get dashboard summary
curl http://localhost:8000/api/dashboard/summary
```

Or visit the interactive docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Step 5: Start the Frontend

In another terminal:

```bash
# Activate venv (if not already)
source .venv/bin/activate

# Start Streamlit
streamlit run frontend/app.py
```

The frontend will automatically:
- Detect the API at `http://localhost:8000`
- Use real data from the API
- Fall back to mock data if API is unavailable

## Troubleshooting

### API won't start
- Make sure venv is activated: `source .venv/bin/activate`
- Check if port 8000 is in use: `lsof -i :8000`
- Use a different port: `python scripts/run_api.py --port 8001`

### Frontend can't connect to API
- Verify API is running: `curl http://localhost:8000/api/health`
- Check API_BASE_URL: `echo $API_BASE_URL`
- Set it manually: `export API_BASE_URL=http://localhost:8000`

### No data showing
- Create sample data: `python scripts/create_sample_data.py`
- Check database: `ls -lh data/bandit_ads.db`

## Next Steps

1. ✅ API is running
2. ✅ Frontend is running
3. Explore the dashboard!
4. Test different endpoints in the API docs
5. Check campaign details and metrics

## Useful Commands

```bash
# Run tests
python scripts/test_api.py

# Check installation
python scripts/check_installation.py

# Create sample data
python scripts/create_sample_data.py

# Start API with auto-reload (development)
python scripts/run_api.py --reload
```
