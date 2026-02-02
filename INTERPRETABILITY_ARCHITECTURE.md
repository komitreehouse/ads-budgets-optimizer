# Human Interpretability Layer - Architecture Design

## Requirements Analysis

### Core Requirements
1. **Read Access**: Query optimizer state, decisions, performance metrics
2. **Write Access**: Analyst feedback, manual overrides, configuration changes
3. **Future-Proof**: Easy integration with monitoring system
4. **Internet Access**: Research trends, investigate external factors
5. **Natural Language**: Conversational interface for queries
6. **Explanations**: Human-readable explanations of decisions

### Use Cases
- "Why did Google Search budget increase by 20%?"
- "Show me ROAS trends for Meta campaigns last week"
- "What's causing the underspend in Campaign X?"
- "I want to manually allocate 30% to Google Search for the next 3 days"
- "Research if there's a social media trend affecting our Meta performance"
- "Compare Google vs Meta performance and explain the difference"

---

## Architecture Options Analysis

### Option 1: Simple LLM with Direct API Access
**Pros:**
- Simple to implement
- Direct access to backend
- Fast responses

**Cons:**
- No structured tool access
- Limited context window
- Hard to maintain tool schemas
- No standardized protocol

**Verdict**: ❌ Too limited for comprehensive read/write access

---

### Option 2: LLM with RAG (Retrieval Augmented Generation)
**Pros:**
- Great for historical context
- Can answer questions about past decisions
- Good for explanation generation

**Cons:**
- Only handles read access (no write)
- Requires vector store maintenance
- Doesn't solve real-time query problem
- No structured operations

**Verdict**: ⚠️ Good component, but not sufficient alone

---

### Option 3: MCP (Model Context Protocol) Server
**Pros:**
- ✅ Standardized protocol for tool access
- ✅ Structured read/write operations
- ✅ Type-safe tool definitions
- ✅ Easy to extend with new tools
- ✅ Works with Claude, GPT-4, etc.
- ✅ Tool discovery and documentation
- ✅ Future-proof (monitoring tools can be added easily)

**Cons:**
- Requires MCP server implementation
- Slightly more complex setup

**Verdict**: ✅ **Best foundation** - provides structured access

---

### Option 4: Hybrid Architecture (Recommended)
**MCP Server + RAG + Direct Queries + Internet Access**

**Components:**
1. **MCP Server**: Structured read/write operations
2. **RAG Layer**: Historical decision explanations
3. **Direct API**: Real-time queries (bypass LLM for speed)
4. **Internet Tools**: Web search, trend analysis
5. **LLM Agent**: Orchestrates between components

**Verdict**: ✅✅ **RECOMMENDED** - Best of all worlds

---

## Recommended Architecture: Hybrid MCP + RAG

```
┌─────────────────────────────────────────────────────────┐
│              LLM Agent (Claude/GPT-4)                  │
│  - Natural language understanding                       │
│  - Query routing                                        │
│  - Response synthesis                                   │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴────────┬──────────────┬──────────────┐
       │                │              │              │
┌──────▼──────┐  ┌─────▼──────┐  ┌───▼──────┐  ┌───▼────────┐
│  MCP Server │  │  RAG Store │  │  Direct  │  │  Internet  │
│             │  │            │  │   API    │  │   Tools    │
│  Tools:     │  │  Vector DB │  │          │  │            │
│  - Read     │  │  - Past    │  │  Fast    │  │  - Search  │
│  - Write    │  │    decisions│  │  queries │  │  - Trends │
│  - Monitor  │  │  - Explanations│          │  │  - News    │
└──────┬──────┘  └─────────────┘  └────┬─────┘  └────────────┘
       │                                │
       └────────────┬───────────────────┘
                    │
        ┌───────────▼────────────┐
        │   Backend Services     │
        │  - Optimizer Service   │
        │  - Database            │
        │  - Monitoring (future) │
        └───────────────────────┘
```

---

## Detailed Architecture Design

### 1. MCP Server (Core Interface)

**Purpose**: Provide structured, type-safe access to optimizer operations

**Implementation**: Python MCP server using `mcp` SDK

**Tools Exposed**:

#### Read Operations
```python
@mcp_tool
def get_campaign_status(campaign_id: int) -> Dict:
    """Get current status and performance of a campaign"""
    
@mcp_tool
def get_allocation_history(campaign_id: int, days: int = 7) -> List[Dict]:
    """Get allocation changes over time with explanations"""
    
@mcp_tool
def get_arm_performance(arm_id: int, start_date: str, end_date: str) -> Dict:
    """Get performance metrics for a specific arm"""
    
@mcp_tool
def explain_allocation_change(change_id: int) -> str:
    """Get human-readable explanation of why allocation changed"""
    
@mcp_tool
def query_metrics(campaign_id: int, metric: str, time_range: str) -> Dict:
    """Query specific metrics (ROAS, CTR, CVR, etc.)"""
    
@mcp_tool
def get_optimizer_state(campaign_id: int) -> Dict:
    """Get current optimizer state (alpha/beta, risk scores, etc.)"""
```

#### Write Operations
```python
@mcp_tool
def suggest_allocation_override(
    campaign_id: int,
    arm_id: int,
    new_allocation: float,
    justification: str
) -> Dict:
    """Analyst suggests a manual allocation override"""
    
@mcp_tool
def pause_campaign(campaign_id: int, reason: str) -> Dict:
    """Pause campaign optimization"""
    
@mcp_tool
def update_campaign_budget(campaign_id: int, new_budget: float) -> Dict:
    """Update campaign budget"""
    
@mcp_tool
def provide_feedback(
    campaign_id: int,
    feedback_type: str,
    message: str,
    context: Dict
) -> Dict:
    """Provide analyst feedback/domain knowledge"""
```

#### Monitoring Operations (Future)
```python
@mcp_tool
def get_alerts(campaign_id: Optional[int] = None) -> List[Dict]:
    """Get active alerts from monitoring system"""
    
@mcp_tool
def investigate_anomaly(alert_id: int) -> Dict:
    """Investigate a specific anomaly/alert"""
```

**Benefits**:
- Type-safe operations
- Auto-generated documentation
- Easy to extend
- Works with any MCP-compatible LLM

---

### 2. RAG Layer (Historical Context)

**Purpose**: Provide context about past decisions and explanations

**Implementation**: 
- Vector store (ChromaDB/Pinecone/Weaviate)
- Embeddings: OpenAI `text-embedding-3-small` or similar
- Documents: Historical allocation changes, explanations, performance summaries

**What Gets Indexed**:
```python
{
    "timestamp": "2026-01-20T10:30:00Z",
    "campaign_id": 1,
    "change_type": "allocation_increase",
    "arm": "Google_Search_CreativeA_1.0",
    "old_allocation": 0.15,
    "new_allocation": 0.20,
    "explanation": "Increased due to Q4 seasonality (1.2x multiplier) and 
                    recent ROAS improvement (2.1 → 2.5). Risk score decreased 
                    from 0.15 to 0.10.",
    "factors": {
        "seasonality": 0.2,
        "roas_improvement": 0.15,
        "risk_reduction": 0.05
    },
    "performance_after": {
        "roas": 2.5,
        "spend": 5000.0
    }
}
```

**Query Flow**:
1. User asks: "Why did Google Search budget increase?"
2. RAG retrieves similar past explanations
3. LLM synthesizes answer using retrieved context + current state

**Benefits**:
- Answers questions about past decisions
- Provides context for similar situations
- Learns from historical patterns

---

### 3. Direct API Layer (Fast Queries)

**Purpose**: Bypass LLM for simple, fast queries

**Implementation**: FastAPI endpoints

**Use Cases**:
- Simple metric queries (no explanation needed)
- Real-time dashboards
- Bulk data exports

**Example**:
```python
GET /api/campaigns/1/metrics?metric=roas&days=7
→ Returns: {"roas": 2.3, "trend": "increasing"}
```

**Benefits**:
- Fast responses (<100ms)
- No LLM cost for simple queries
- Can be used by dashboards directly

---

### 4. Internet Access Tools

**Purpose**: Research external factors, trends, investigate behavior

**MCP Tools**:
```python
@mcp_tool
def web_search(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web for information"""
    
@mcp_tool
def analyze_trend(topic: str, platform: str = "google") -> Dict:
    """Analyze trends for a topic (Google Trends, Twitter, etc.)"""
    
@mcp_tool
def research_competitor(competitor_name: str) -> Dict:
    """Research competitor advertising strategies"""
```

**Use Cases**:
- "Is there a social media trend affecting Meta performance?"
- "What's happening with Google Ads pricing this week?"
- "Research competitor strategies in Q4"

**Implementation**: 
- Use Tavily API or similar for web search
- Google Trends API for trend analysis
- Twitter API for social trends (optional)

---

### 5. LLM Agent (Orchestrator)

**Purpose**: Understand queries, route to appropriate tools, synthesize responses

**Implementation**: 
- Claude 3.5 Sonnet or GPT-4 Turbo
- MCP client to connect to MCP server
- RAG retrieval integration
- Tool calling for internet access

**Query Flow**:
```
User: "Why did Google Search budget increase by 20%?"

1. LLM analyzes query → needs explanation + current state
2. LLM calls MCP tools:
   - get_allocation_history(campaign_id, days=7)
   - explain_allocation_change(change_id)
3. LLM queries RAG for similar past explanations
4. LLM synthesizes answer:
   "The Google Search budget increased by 20% due to three factors:
    - Q4 seasonality multiplier (1.2x) applied
    - Recent ROAS improvement from 2.1 to 2.5
    - Risk score decreased from 0.15 to 0.10, indicating more confidence"
```

---

## Implementation Plan

### Phase 1: MCP Server Foundation (Week 1)
1. Set up MCP server infrastructure
2. Implement read operations (get_campaign_status, get_allocation_history, etc.)
3. Test with Claude/GPT-4
4. Document tool schemas

### Phase 2: Write Operations (Week 1-2)
1. Implement write operations (suggest_allocation_override, etc.)
2. Add validation and security
3. Test analyst feedback flow

### Phase 3: RAG Integration (Week 2)
1. Set up vector store
2. Index historical decisions/explanations
3. Implement retrieval
4. Integrate with LLM agent

### Phase 4: Internet Access (Week 2-3)
1. Add web search tool
2. Add trend analysis tool
3. Test research capabilities

### Phase 5: LLM Agent (Week 3)
1. Set up LLM agent with MCP client
2. Implement query routing
3. Add response synthesis
4. Test end-to-end queries

### Phase 6: Polish & Testing (Week 4)
1. Error handling
2. Performance optimization
3. User testing
4. Documentation

---

## Technology Stack

### Core
- **MCP SDK**: `@modelcontextprotocol/sdk` (Python)
- **LLM**: Claude 3.5 Sonnet (via Anthropic API) or GPT-4 Turbo
- **Vector Store**: ChromaDB (local) or Pinecone (cloud)
- **Embeddings**: OpenAI `text-embedding-3-small`

### Internet Access
- **Web Search**: Tavily API or Serper API
- **Trends**: Google Trends API (unofficial) or Twitter API

### Backend Integration
- **Optimizer Service**: Direct Python imports
- **Database**: SQLAlchemy (already in use)
- **API**: FastAPI for direct queries

---

## Example Interactions

### Example 1: Explanation Query
```
User: "Why did Google Search budget increase?"

Agent:
1. Calls get_allocation_history(campaign_id=1, days=7)
2. Retrieves recent allocation changes
3. Calls explain_allocation_change(change_id=123)
4. Queries RAG for similar past decisions
5. Synthesizes:

"The Google Search budget increased by 20% (from $1,500 to $1,800) on 
January 22nd. This change was driven by:

1. **Q4 Seasonality Effect**: The Q4 multiplier (1.2x) is now active, 
   historically increasing Search performance by 20% during this period.

2. **ROAS Improvement**: Recent performance shows ROAS improved from 2.1 to 2.5 
   over the past week, indicating strong performance.

3. **Risk Reduction**: The risk score decreased from 0.15 to 0.10, giving the 
   optimizer more confidence in this arm.

Similar patterns were observed in Q4 2025, where seasonality-driven increases 
led to 15% better overall campaign performance."
```

### Example 2: Analyst Override
```
User: "I want to allocate 30% to Google Search for the next 3 days because 
       we're running a special promotion"

Agent:
1. Calls suggest_allocation_override(
     campaign_id=1,
     arm_id=5,
     new_allocation=0.30,
     justification="Special promotion running"
   )
2. Confirms override is set
3. Explains impact:

"I've set a manual override to allocate 30% of budget to Google Search for 
the next 3 days (until January 27th). 

**Impact Analysis:**
- Current allocation: 20%
- New allocation: 30%
- Expected additional spend: ~$500/day
- Based on current ROAS (2.5), this could generate ~$1,250/day additional revenue

The override will automatically expire on January 27th, and the optimizer will 
resume normal operation. I'll track the performance impact and report back."
```

### Example 3: Research Query
```
User: "Is there a social media trend affecting our Meta performance?"

Agent:
1. Calls get_arm_performance(arm_id=10, start_date="2026-01-17", end_date="2026-01-24")
2. Sees Meta performance declined
3. Calls web_search("Meta ads performance January 2026 social media trends")
4. Calls analyze_trend("Meta advertising", platform="twitter")
5. Synthesizes:

"Your Meta performance has declined 15% over the past week. I researched 
current trends and found:

**Key Findings:**
1. **Algorithm Changes**: Meta rolled out new ad ranking algorithm on Jan 20th, 
   affecting many advertisers' performance.

2. **Competition**: Increased competition in Q4 (typical) + new algorithm = 
   higher CPCs and lower reach.

3. **Social Trends**: Twitter/X discussions show similar complaints from 
   advertisers about Meta performance drops.

**Recommendations:**
- Consider temporarily reducing Meta allocation until algorithm stabilizes
- Increase Google Search allocation (currently performing well)
- Monitor for 2-3 more days to see if it's temporary

Would you like me to suggest a reallocation?"
```

---

## Security & Validation

### Read Operations
- ✅ Campaign access control (user can only query their campaigns)
- ✅ Rate limiting
- ✅ Query validation

### Write Operations
- ✅ Authentication required
- ✅ Justification required for overrides
- ✅ Audit logging (who changed what, when, why)
- ✅ Approval workflow for major changes (optional)
- ✅ Rollback capability

---

## Advantages of This Architecture

1. **Structured Access**: MCP provides type-safe, documented operations
2. **Extensible**: Easy to add new tools (monitoring, etc.)
3. **Context-Aware**: RAG provides historical context
4. **Fast**: Direct API for simple queries
5. **Intelligent**: LLM handles complex reasoning
6. **Research Capable**: Internet access for external factors
7. **Future-Proof**: Monitoring tools can be added as MCP tools
8. **Standardized**: MCP is becoming industry standard

---

## Questions for You

1. **LLM Preference**: Claude 3.5 Sonnet or GPT-4 Turbo? (Claude better for long context, GPT-4 better for tool use)

2. **Vector Store**: Local (ChromaDB) or cloud (Pinecone)? (Local = simpler, Cloud = scalable)

3. **Internet Access**: Which services? (Tavily for search, Google Trends, Twitter API?)

4. **Security**: Do you need multi-user support with access control, or single-user initially?

5. **Approval Workflow**: Should analyst overrides require approval, or auto-apply?

---

## Recommendation

**Go with Hybrid MCP + RAG Architecture**

**Why:**
- ✅ Best balance of structure and flexibility
- ✅ Future-proof (easy to add monitoring tools)
- ✅ Comprehensive read/write access
- ✅ Natural language interface
- ✅ Historical context via RAG
- ✅ Internet research capability
- ✅ Industry-standard (MCP)

**Start with:**
1. MCP Server with read operations
2. Basic LLM agent
3. Then add RAG, write operations, internet access

This gives you a working system quickly, then you can enhance incrementally.
