# API Setup Guide

## Overview

The Ads Budget Optimizer now has a REST API layer that connects the frontend to the backend services. The API is built with FastAPI and provides endpoints for campaigns, dashboard data, recommendations, and optimizer status.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install FastAPI, uvicorn, and other required packages.

### 2. Start the API Server

```bash
# From project root
python scripts/run_api.py

# Or with custom host/port
python scripts/run_api.py --host 0.0.0.0 --port 8000

# For development with auto-reload
python scripts/run_api.py --reload
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)

### 3. Start the Frontend

The frontend will automatically detect if the API is running and use it instead of mock data.

```bash
# From project root
cd frontend
streamlit run app.py
```

Or if running from project root:
```bash
streamlit run frontend/app.py
```

## API Endpoints

### Campaigns

- `GET /api/campaigns` - List all campaigns
- `GET /api/campaigns/{id}` - Get campaign details
- `GET /api/campaigns/{id}/metrics?time_range=7D` - Get campaign metrics
- `GET /api/campaigns/{id}/time-series?time_range=7D` - Get time-series data
- `GET /api/campaigns/{id}/arms` - Get all arms for a campaign
- `GET /api/campaigns/{id}/allocation` - Get budget allocation

### Dashboard

- `GET /api/dashboard/summary` - Dashboard summary metrics
- `GET /api/dashboard/brand-budget?time_range=MTD` - Brand budget overview
- `GET /api/dashboard/channel-splits?time_range=MTD` - Channel budget splits

### Recommendations

- `GET /api/recommendations?status=pending` - Get recommendations
- `GET /api/recommendations/pending` - Get pending recommendations
- `POST /api/recommendations/{id}/approve` - Approve recommendation
- `POST /api/recommendations/{id}/reject` - Reject recommendation

### Optimizer

- `GET /api/optimizer/status` - Get optimizer status
- `GET /api/optimizer/decisions?limit=5` - Get recent decisions
- `GET /api/optimizer/factor-attribution` - Get factor attribution

### Health

- `GET /api/health` - Health check endpoint

## Configuration

### Environment Variables

You can configure the API base URL for the frontend:

```bash
export API_BASE_URL=http://localhost:8000
```

Or set it in your environment before running the frontend.

### CORS

The API is configured to allow CORS from any origin (for development). In production, update the CORS settings in `src/bandit_ads/api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Production URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:8000/api/health

# Get campaigns
curl http://localhost:8000/api/campaigns

# Get dashboard summary
curl http://localhost:8000/api/dashboard/summary
```

### Using the Interactive Docs

Visit `http://localhost:8000/docs` to use the Swagger UI for interactive API testing.

## Frontend Integration

The frontend's `data_service.py` automatically detects if the API is running:

1. It tries to connect to the API at startup
2. If successful, it uses API calls
3. If the API is not available, it falls back to mock data

This allows the frontend to work in development mode even without the API running.

## Troubleshooting

### API not starting

- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check database connection: Ensure database is initialized

### Frontend not connecting to API

- Verify API is running: `curl http://localhost:8000/api/health`
- Check API_BASE_URL environment variable
- Check browser console for CORS errors
- Verify API and frontend are on same network/domain

### Database errors

- Initialize database: `python -c "from src.bandit_ads.database import init_database; init_database(create_tables=True)"`
- Check database file exists: `ls data/bandit_ads.db`

## Next Steps

1. **Add Authentication**: Implement API key or OAuth authentication
2. **Add Rate Limiting**: Prevent API abuse
3. **Add Request Logging**: Track API usage
4. **Add Caching**: Improve performance for frequently accessed data
5. **Add WebSocket Support**: For real-time updates

## Development Notes

- The API uses FastAPI's automatic OpenAPI documentation
- All endpoints return JSON
- Error responses follow a consistent format
- The API is stateless (no session management yet)
