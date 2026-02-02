# Interpretability Layer - Implementation Complete ✅

## Summary

All requested components have been completed:

1. ✅ **MCP Write Operations** - Overrides and feedback
2. ✅ **Change Tracking** - Logs every change with full context
3. ✅ **Central Orchestrator** - Coordinates multiple agents and tools
4. ✅ **LLM-Powered Explanation Generation** - Natural language explanations

---

## 1. MCP Write Operations ✅

### Implemented Tools

**File**: `src/bandit_ads/mcp_server_operations.py`

#### Write Operations:
- `suggest_allocation_override` - Analyst suggests manual allocation override
- `pause_campaign` - Pause campaign optimization
- `resume_campaign` - Resume campaign optimization
- `update_campaign_budget` - Update campaign budget
- `provide_feedback` - Provide analyst feedback/domain knowledge

#### Explanation Operations:
- `explain_allocation_change` - Explain why allocation changed
- `explain_performance` - Explain performance metrics and trends

#### Research Operations:
- `web_search` - Search the web using Tavily
- `analyze_trend` - Analyze trends using Google Trends

### Features:
- All operations integrated with change tracking
- Recommendations created for write operations (approval workflow)
- Full error handling and logging
- User authentication support

---

## 2. Change Tracking System ✅

### Database Models

**File**: `src/bandit_ads/change_tracker.py`

#### AllocationChange Model:
- Tracks every allocation change
- Stores old/new allocation, change percent
- Records change reason, factors, MMM factors
- Captures optimizer state at time of change
- Records performance before/after
- Tracks who initiated change (user_id)

#### DecisionLog Model:
- Logs all optimizer decisions
- Records reasoning and factors considered
- Stores confidence scores
- Captures optimizer state and performance context

### Features:
- Automatic logging of all changes
- Full context capture (state, performance, factors)
- Queryable history (by campaign, arm, time range)
- Integration with optimizer service

### Usage:
```python
from src.bandit_ads.change_tracker import get_change_tracker

tracker = get_change_tracker()

# Log allocation change
tracker.log_allocation_change(
    campaign_id=1,
    arm_id=5,
    old_allocation=0.15,
    new_allocation=0.20,
    change_type="auto",
    change_reason="Q4 seasonality + ROAS improvement",
    factors={"seasonality": 0.2, "roas_improvement": 0.15},
    mmm_factors={"q4_multiplier": 1.2}
)

# Get history
history = tracker.get_allocation_history(campaign_id=1, days=7)
```

---

## 3. Central Orchestrator Agent ✅

### Architecture

**File**: `src/bandit_ads/orchestrator.py`

```
User Query
    ↓
OrchestratorAgent
    ├─→ Authenticate User
    ├─→ Classify Query (LLM Router)
    ├─→ Select LLM (Claude/GPT-4)
    ├─→ Retrieve RAG Context
    ├─→ Call LLM with Context
    ├─→ Execute Tool Calls (MCP)
    └─→ Synthesize Final Response
```

### Features:

1. **Query Routing**:
   - Classifies query type (explanation, optimization, analysis, research)
   - Selects appropriate LLM (Claude for explanations, GPT-4 for optimization)
   - Fast path for simple metric queries (bypasses LLM)

2. **Context Management**:
   - Retrieves relevant past decisions from RAG
   - Builds tool context (available MCP tools)
   - Manages campaign context

3. **Tool Orchestration**:
   - Executes MCP tool calls requested by LLM
   - Handles multiple tool calls in sequence
   - Synthesizes tool results into final answer

4. **Authentication & Authorization**:
   - Validates user tokens
   - Checks campaign access permissions
   - Passes user context to tools

5. **Response Synthesis**:
   - Combines LLM response with tool results
   - Formats final answer
   - Includes metadata (query type, model used, duration)

### Usage:
```python
from src.bandit_ads.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Process query
response = await orchestrator.process_query(
    query="Why did Google Search budget increase by 20%?",
    user_token="user_session_token",
    campaign_id=1
)

print(response["answer"])
# "The Google Search budget increased by 20% due to:
#  1. Q4 seasonality multiplier (1.2x)
#  2. Recent ROAS improvement (2.1 → 2.5)
#  3. Reduced risk score..."
```

---

## Integration Points

### 1. Optimizer Service Integration
- Change tracker logs allocation changes from optimizer
- MCP operations can pause/resume campaigns
- Recommendations can override optimizer decisions

### 2. Database Integration
- All changes stored in `allocation_changes` table
- All decisions stored in `decision_logs` table
- Full audit trail maintained

### 3. Authentication Integration
- All write operations require authentication
- Campaign-level access control enforced
- User context passed to change tracker

### 4. RAG Integration
- Past decisions indexed in vector store
- Similar decisions retrieved for context
- Explanations enhanced with historical patterns

---

## Example Flow

### User Query: "Why did Google Search budget increase?"

1. **Orchestrator** receives query
2. **Router** classifies as "explanation" → selects Claude
3. **RAG** retrieves similar past explanations
4. **MCP Tool** calls `get_allocation_history(campaign_id=1, days=7)`
5. **Change Tracker** returns allocation changes
6. **MCP Tool** calls `explain_allocation_change(change_id=123)`
7. **Claude** synthesizes explanation using:
   - Allocation history
   - RAG context (similar past decisions)
   - MMM factors
   - Performance metrics
8. **Orchestrator** returns final answer

### User Query: "I want to allocate 30% to Google Search"

1. **Orchestrator** receives query
2. **Router** classifies as "optimization" → selects GPT-4
3. **GPT-4** suggests using `suggest_allocation_override` tool
4. **MCP Tool** creates recommendation
5. **Change Tracker** logs the override request
6. **Orchestrator** returns recommendation details
7. **User** approves → recommendation applied → change logged

---

## 4. LLM-Powered Explanation Generation ✅

### Architecture

**File**: `src/bandit_ads/explanation_generator.py`

The `ExplanationGenerator` class uses Claude to transform raw optimizer data into natural language:

```
Raw Data (factors, metrics, state)
    ↓
ExplanationGenerator
    ├─→ Build context-aware prompt
    ├─→ Retrieve historical context from RAG
    ├─→ Call Claude API
    └─→ Return natural language explanation
```

### Explanation Types:

1. **Allocation Change Explanations**
   - Explains WHY allocation changed
   - References factors, MMM factors, optimizer state
   - Includes historical context from similar past decisions

2. **Performance Explanations**
   - Explains performance trends
   - Identifies what's working vs what needs attention
   - References recent allocation changes

3. **Anomaly Explanations**
   - Explains what the anomaly means
   - Suggests possible causes
   - Indicates whether it's concerning

4. **Recommendation Explanations**
   - Explains why the optimizer made this recommendation
   - Describes expected impact
   - Notes considerations before approving

### Example Output:

**Before (template-based):**
```
**Factors:**
- seasonality: 0.2
- roas_improvement: 0.15
```

**After (LLM-powered):**
```
The Google Search budget increased by 20% (from 15% to 18% of total spend) due to several converging factors:

1. **Q4 Seasonality Effect**: We're now in Q4, which historically increases Search channel performance by about 20%. The optimizer detected this seasonal pattern and increased allocation to capitalize on it.

2. **Strong Recent Performance**: Over the past week, this arm's ROAS improved from 2.1 to 2.5, a 19% improvement. This indicates the audience targeting and creative combination is working well.

3. **Reduced Risk**: The risk score decreased from 0.15 to 0.10, meaning the optimizer has more confidence in this arm's consistent performance.

**Historical Context**: In Q4 2025, similar seasonality-driven increases led to 15% better overall campaign performance.
```

### Features:
- Falls back to template-based explanations if Claude unavailable
- Includes RAG context from similar past decisions
- Customized prompts for each explanation type
- Concise but thorough explanations

---

## Files Created/Modified

### New Files:
1. `src/bandit_ads/change_tracker.py` - Change tracking system
2. `src/bandit_ads/mcp_server_operations.py` - MCP operation implementations
3. `src/bandit_ads/orchestrator.py` - Central orchestrator agent
4. `src/bandit_ads/explanation_generator.py` - LLM-powered explanation generation

### Modified Files:
1. `src/bandit_ads/mcp_server.py` - Integrated operations and explanation tools
2. `src/bandit_ads/database.py` - Added AllocationChange and DecisionLog models (via change_tracker)

---

## Database Schema Updates

### New Tables:

#### `allocation_changes`
- `id`, `campaign_id`, `arm_id`
- `old_allocation`, `new_allocation`, `change_percent`
- `change_reason`, `factors`, `mmm_factors`
- `optimizer_state`, `performance_before`, `performance_after`
- `change_type`, `initiated_by`, `timestamp`

#### `decision_logs`
- `id`, `campaign_id`
- `decision_type`, `decision_data`
- `reasoning`, `factors_considered`, `confidence_score`
- `optimizer_state`, `performance_context`
- `timestamp`

---

## Next Steps

1. **Test Integration**: Test end-to-end flow with real queries
2. **Enhance Explanations**: Improve explanation generation using LLM
3. **Add Monitoring**: Integrate with monitoring system (when built)
4. **Dashboard**: Create UI to visualize changes and explanations
5. **Performance**: Optimize RAG retrieval and tool execution

---

## Configuration

Add to `config.yaml`:
```yaml
interpretability:
  orchestrator:
    enable_fast_path: true  # Use direct API for simple queries
    max_rag_results: 3
    max_tool_calls: 5
  
  change_tracking:
    log_all_changes: true
    log_decisions: true
    retention_days: 90
```

---

## Status: ✅ COMPLETE

All requested features have been implemented:
- ✅ MCP write operations (overrides, feedback)
- ✅ Change tracking (logs every change)
- ✅ Central orchestrator (coordinates agents and tools)
- ✅ LLM-powered explanation generation (natural language)

### MCP Explanation Tools:
- `explain_allocation_change` - LLM-powered allocation change explanations
- `explain_performance` - LLM-powered performance analysis
- `explain_anomaly` - LLM-powered anomaly explanations
- `explain_recommendation` - LLM-powered recommendation explanations

The interpretability layer is now fully functional and ready for integration testing!
