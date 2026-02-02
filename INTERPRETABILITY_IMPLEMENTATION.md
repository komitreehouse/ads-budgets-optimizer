# Interpretability Layer - Implementation Status

## ✅ Completed Components

### 1. MCP Server Foundation (`src/bandit_ads/mcp_server.py`)
**Status**: Core structure complete, read operations implemented

**Features**:
- MCP server setup with tool registration
- Read operations:
  - `get_campaign_status` - Get campaign status and performance
  - `get_allocation_history` - Get allocation changes over time (placeholder)
  - `get_arm_performance` - Get performance metrics for an arm
  - `query_metrics` - Query specific metrics (ROAS, CTR, etc.)
  - `get_optimizer_state` - Get optimizer state (alpha/beta, risk scores)

**Next Steps**:
- Complete allocation history tracking
- Add write operations
- Add explanation operations
- Add research operations

---

### 2. LLM Router (`src/bandit_ads/llm_router.py`)
**Status**: Complete ✅

**Features**:
- Query classification (explanation, optimization, analysis, research, metric_query)
- Model selection:
  - Claude 4.5 Sonnet: Explanations, analysis, research
  - GPT-4 Turbo: Optimization logic, structured planning
- Keyword-based classification
- Direct API routing for simple queries

**Usage**:
```python
from src.bandit_ads.llm_router import get_llm_router

router = get_llm_router()
model = router.select_model("Why did Google Search budget increase?")
# Returns: "claude-3-5-sonnet-20241022"
```

---

### 3. Vector Store (`src/bandit_ads/vector_store.py`)
**Status**: Complete ✅

**Features**:
- Swappable interface (VectorStoreInterface)
- ChromaDB implementation (local, default)
- Pinecone implementation (cloud, ready for swap)
- Easy store swapping via `swap_store()`
- Decision explanation indexing
- Similar decision search

**Usage**:
```python
from src.bandit_ads.vector_store import get_vector_store

# Default: ChromaDB (local)
store = get_vector_store()

# Add decision explanation
store.add_decision_explanation(
    campaign_id=1,
    arm_id=5,
    change_type="allocation_increase",
    explanation="Increased due to Q4 seasonality",
    factors={"seasonality": 0.2, "roas_improvement": 0.15}
)

# Search similar decisions
results = store.search_similar_decisions("Why did budget increase?", campaign_id=1)

# Swap to Pinecone (if needed)
store.swap_store("pinecone", api_key="...", index_name="...")
```

---

### 4. Authentication & Access Control (`src/bandit_ads/auth.py`)
**Status**: Complete ✅

**Features**:
- Multi-user support
- Role-based access control (admin, analyst, viewer)
- Campaign-level access control
- Session management
- Password hashing
- User creation and authentication

**Database Models**:
- `User` - User accounts
- `CampaignAccess` - Campaign-level permissions
- `Session` - User sessions

**Usage**:
```python
from src.bandit_ads.auth import get_auth_manager

auth = get_auth_manager()

# Create user
user = auth.create_user("analyst@example.com", "analyst1", "password", role="analyst")

# Authenticate
session = auth.authenticate("analyst@example.com", "password")

# Check access
user = auth.get_user_from_token(session.token)
has_access = auth.check_access(user, campaign_id=1, operation="write")
```

---

### 5. Research Tools (`src/bandit_ads/research_tools.py`)
**Status**: Complete ✅

**Features**:
- Tavily API integration (web search)
- Google Trends integration (pytrends)
- Combined research tool
- Trend analysis
- Keyword comparison

**Usage**:
```python
from src.bandit_ads.research_tools import get_research_tools

research = get_research_tools()

# Research a topic
results = research.research_topic(
    "Meta ads performance January 2026",
    include_trends=True,
    max_search_results=5
)

# Web search only
search_results = research.tavily.search("Google Ads algorithm changes")

# Trends only
trend_data = research.google_trends.get_trend("Meta advertising", timeframe="today 7-d")
```

**Environment Variables**:
- `TAVILY_API_KEY` - Tavily API key (required for web search)

---

### 6. Recommendation System (`src/bandit_ads/recommendations.py`)
**Status**: Core complete, needs integration ✅

**Features**:
- Recommendation generation
- Approval workflow
- Auto-apply option
- Recommendation expiration
- Status tracking (pending, approved, rejected, applied, expired)

**Database Model**:
- `Recommendation` - Stores recommendations

**Usage**:
```python
from src.bandit_ads.recommendations import get_recommendation_manager

manager = get_recommendation_manager()

# Create recommendation
rec = manager.create_recommendation(
    campaign_id=1,
    recommendation_type="allocation_change",
    title="Increase Google Search allocation",
    description="ROAS improved 20%, recommend increasing allocation",
    details={"arm_id": 5, "new_allocation": 0.30},
    auto_apply=False,
    expires_in_hours=24
)

# Approve recommendation
manager.approve_recommendation(rec.id, user_id=1)

# Reject recommendation
manager.reject_recommendation(rec.id, user_id=1, reason="Not enough data")
```

---

## 🚧 In Progress / Next Steps

### 1. Complete MCP Server Write Operations
**Priority**: HIGH
**Estimated Time**: 2-3 days

**To Implement**:
- `suggest_allocation_override` - Analyst override tool
- `pause_campaign` - Pause campaign tool
- `update_campaign_budget` - Budget update tool
- `provide_feedback` - Analyst feedback tool

### 2. Complete MCP Server Explanation Operations
**Priority**: HIGH
**Estimated Time**: 2-3 days

**To Implement**:
- `explain_allocation_change` - Explain why allocation changed
- `explain_performance` - Explain performance metrics
- `explain_anomaly` - Explain anomalies

### 3. Complete MCP Server Research Operations
**Priority**: MEDIUM
**Estimated Time**: 1-2 days

**To Implement**:
- `web_search` - Web search tool
- `analyze_trend` - Trend analysis tool
- `research_competitor` - Competitor research tool

### 4. LLM Agent Orchestrator
**Priority**: HIGH
**Estimated Time**: 3-5 days

**To Implement**:
- Main agent class that orchestrates MCP tools
- Query understanding and routing
- Response synthesis
- Integration with Claude/GPT-4 APIs

### 5. Allocation Change Tracking
**Priority**: HIGH
**Estimated Time**: 2-3 days

**To Implement**:
- Track allocation changes in database
- Store explanations with changes
- Link to MMM factors
- Generate explanations

---

## 📋 Architecture Summary

```
┌─────────────────────────────────────────┐
│         LLM Agent Orchestrator          │
│  - Query understanding                  │
│  - Tool routing                         │
│  - Response synthesis                   │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┬──────────────┬──────────────┐
       │                │              │              │
┌──────▼──────┐  ┌─────▼──────┐  ┌───▼──────┐  ┌───▼────────┐
│  MCP Server │  │  RAG Store │  │  Direct │  │  Research  │
│             │  │            │  │   API   │  │   Tools    │
│  Tools:     │  │  ChromaDB  │  │         │  │            │
│  - Read ✅  │  │  (Local)   │  │  Fast   │  │  - Tavily  │
│  - Write ⏳ │  │            │  │  queries │  │  - Trends  │
│  - Explain ⏳│  │            │  │         │  │            │
│  - Research ⏳│  └─────────────┘  └─────────┘  └────────────┘
└──────┬──────┘
       │
┌──────▼──────────┐
│   Backend       │
│  - Optimizer    │
│  - Database     │
│  - Auth         │
└─────────────────┘
```

---

## 🔧 Configuration

Add to `config.yaml`:
```yaml
interpretability:
  llm:
    claude_model: "claude-3-5-sonnet-20241022"
    gpt4_model: "gpt-4-turbo-preview"
    claude_api_key: "${ANTHROPIC_API_KEY}"
    openai_api_key: "${OPENAI_API_KEY}"
  
  vector_store:
    type: "chromadb"  # or "pinecone"
    collection_name: "optimizer_decisions"
    persist_directory: "./data/vector_store"
  
  research:
    tavily_api_key: "${TAVILY_API_KEY}"
    enable_trends: true
  
  recommendations:
    default_expiry_hours: 24
    auto_apply_enabled: false
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export ANTHROPIC_API_KEY="your_claude_key"
export OPENAI_API_KEY="your_openai_key"
export TAVILY_API_KEY="your_tavily_key"
```

### 3. Initialize Database Tables
```python
from src.bandit_ads.database import init_database
from src.bandit_ads.auth import User, CampaignAccess, Session
from src.bandit_ads.recommendations import Recommendation

db_manager = init_database(create_tables=True)
# Tables will be created automatically
```

### 4. Create Initial User
```python
from src.bandit_ads.auth import get_auth_manager

auth = get_auth_manager()
auth.create_user("admin@example.com", "admin", "password", role="admin")
```

### 5. Start MCP Server
```python
from src.bandit_ads.mcp_server import get_mcp_server
from src.bandit_ads.utils import ConfigManager

config = ConfigManager('config.yaml')
server = get_mcp_server(config)
await server.run()
```

---

## 📝 Notes

### LLM Switching
- Router automatically selects model based on query type
- Can be extended to support more sophisticated routing
- Future: Add confidence scores and fallback logic

### Vector Store Swapping
- Currently uses ChromaDB (local)
- Can swap to Pinecone by calling `swap_store("pinecone", ...)`
- All code uses interface, so swapping is transparent

### Authentication
- Uses simple password hashing (SHA256)
- For production, consider bcrypt or Argon2
- Session tokens expire after 7 days

### Recommendations
- Recommendations can be auto-applied if user sets preference
- Expire after configurable time period
- Track approval/rejection for learning

---

## 🐛 Known Issues / Limitations

1. **MCP SDK**: Actual MCP SDK API may differ - needs verification
2. **Allocation Tracking**: Allocation change tracking not yet implemented
3. **Explanation Generation**: Needs integration with optimizer state
4. **LLM Agent**: Main orchestrator not yet implemented
5. **Password Security**: Using SHA256 - should upgrade to bcrypt

---

## 🔄 Next Actions

1. **Complete MCP write operations** - Critical for analyst feedback
2. **Implement allocation change tracking** - Needed for explanations
3. **Build LLM agent orchestrator** - Core of the interpretability layer
4. **Add explanation generation** - Key feature for users
5. **Test end-to-end flow** - Verify everything works together

---

**Last Updated**: 2026-01-24
**Status**: Foundation Complete, Core Features In Progress
