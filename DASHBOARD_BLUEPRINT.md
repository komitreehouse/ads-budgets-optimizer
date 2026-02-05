# Dashboard Blueprint - Ads Budget Optimizer

## Design Inspiration
Based on Mixpanel's clean, modern analytics dashboard aesthetic:
- Clean white/light background
- Purple/violet accent color for primary actions
- Left sidebar navigation
- Card-based metric displays with sparklines
- Time range selectors
- Tooltips on hover for charts
- Right sidebar for filters/configuration

---

## 1. Information Architecture

### Primary Views

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NAVIGATION STRUCTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  HOME (Overview)                                                     │
│  ├── Greeting + Summary Stats                                        │
│  ├── Recent Campaigns (cards)                                        │
│  ├── Key Metrics Overview (ROAS, Spend, Conversions)                │
│  └── Recent Alerts / Recommendations                                 │
│                                                                      │
│  CAMPAIGNS                                                           │
│  ├── Campaign List (table)                                           │
│  ├── Campaign Detail View                                            │
│  │   ├── Performance Metrics (charts)                                │
│  │   ├── Allocation Breakdown (pie/bar)                              │
│  │   ├── Arm Performance Comparison                                  │
│  │   └── Recent Changes + Explanations                               │
│  └── Campaign Settings                                               │
│                                                                      │
│  OPTIMIZER                                                           │
│  ├── Optimizer Status (running/paused)                               │
│  ├── Decision Log (why changes were made)                            │
│  ├── Allocation History (timeline)                                   │
│  └── Factor Attribution (what's driving decisions)                   │
│                                                                      │
│  ASK (Natural Language Query)                                        │
│  ├── Query Input                                                     │
│  ├── Response Display                                                │
│  └── Query History                                                   │
│                                                                      │
│  RECOMMENDATIONS                                                     │
│  ├── Pending Recommendations (approval queue)                        │
│  ├── Applied Recommendations                                         │
│  └── Rejected Recommendations                                        │
│                                                                      │
│  ALERTS (Future - Monitoring)                                        │
│  ├── Active Alerts                                                   │
│  ├── Alert History                                                   │
│  └── Alert Configuration                                             │
│                                                                      │
│  SETTINGS                                                            │
│  ├── User Profile                                                    │
│  ├── API Connections                                                 │
│  └── Preferences                                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Hierarchy

### 2.1 App Shell

```
App
├── Sidebar (collapsible)
│   ├── Logo
│   ├── NavItem (Home)
│   ├── NavItem (Campaigns)
│   ├── NavItem (Optimizer)
│   ├── NavItem (Ask)
│   ├── NavItem (Recommendations)
│   ├── NavItem (Alerts) [badge with count]
│   ├── Divider
│   ├── PinnedCampaigns
│   │   └── CampaignLink[]
│   ├── Divider
│   └── UserMenu
│       ├── UserAvatar
│       ├── Settings
│       └── Logout
│
├── TopBar
│   ├── PageTitle
│   ├── SearchBox (⌘+K)
│   ├── TimeRangeSelector
│   └── RefreshButton
│
└── MainContent
    └── [Page-specific content]
```

### 2.2 Home Page Components

```
HomePage
├── GreetingHeader
│   ├── TimeBasedGreeting ("Good Morning")
│   └── UserName
│
├── SummaryMetricsRow
│   ├── MetricCard (Total Spend Today)
│   │   ├── Value
│   │   ├── Trend (vs yesterday)
│   │   └── Sparkline
│   ├── MetricCard (Total ROAS)
│   ├── MetricCard (Active Campaigns)
│   └── MetricCard (Pending Recommendations)
│
├── RecentCampaignsSection
│   ├── SectionHeader ("Your Campaigns")
│   └── CampaignCardGrid
│       └── CampaignCard[]
│           ├── Thumbnail (mini chart)
│           ├── Name
│           ├── Status badge
│           └── Key metric
│
├── RecentChangesSection
│   ├── SectionHeader ("Recent Optimizer Decisions")
│   └── ChangeList
│       └── ChangeItem[]
│           ├── Timestamp
│           ├── Description
│           ├── Explanation (truncated)
│           └── ViewMoreLink
│
└── RecommendationsPreview
    ├── SectionHeader ("Pending Recommendations")
    └── RecommendationList (max 3)
        └── RecommendationCard[]
            ├── Title
            ├── Description
            ├── ApproveButton
            └── RejectButton
```

### 2.3 Campaign Detail Page Components

```
CampaignDetailPage
├── CampaignHeader
│   ├── CampaignName
│   ├── StatusBadge (active/paused)
│   ├── ActionButtons
│   │   ├── PauseButton
│   │   ├── EditButton
│   │   └── MoreMenu
│   └── TimeRangeSelector
│
├── MetricsOverview
│   ├── MetricCard (ROAS)
│   ├── MetricCard (Spend)
│   ├── MetricCard (Revenue)
│   ├── MetricCard (Conversions)
│   ├── MetricCard (CTR)
│   └── MetricCard (CVR)
│
├── PerformanceChartSection
│   ├── ChartTypeSelector (Line/Bar/Area)
│   ├── MetricSelector (ROAS/Spend/etc)
│   ├── MainChart
│   │   ├── TimeSeriesChart
│   │   └── Tooltip (on hover)
│   └── ChartLegend
│
├── AllocationSection
│   ├── SectionHeader ("Budget Allocation")
│   ├── AllocationPieChart
│   │   └── Tooltip (arm details)
│   ├── AllocationTable
│   │   └── ArmRow[]
│   │       ├── ArmName
│   │       ├── Platform icon
│   │       ├── CurrentAllocation
│   │       ├── ChangeIndicator (+/-%)
│   │       ├── Performance (ROAS)
│   │       └── ActionMenu
│   └── SuggestOverrideButton
│
├── ArmPerformanceSection
│   ├── SectionHeader ("Arm Performance")
│   ├── ComparisonChart (bar chart)
│   └── ArmDetailCards
│       └── ArmCard[]
│           ├── Platform/Channel
│           ├── Metrics
│           └── TrendIndicator
│
├── ExplanationsSection
│   ├── SectionHeader ("Why These Allocations?")
│   └── ExplanationPanel
│       ├── LatestExplanation
│       │   ├── Timestamp
│       │   ├── NaturalLanguageText
│       │   └── FactorsList
│       └── ViewHistoryLink
│
└── RightSidebar (optional, like Mixpanel)
    ├── FiltersPanel
    │   ├── PlatformFilter
    │   ├── ChannelFilter
    │   └── DateFilter
    └── QuickActions
        ├── ExportData
        └── ShareLink
```

### 2.4 Ask (NLP Query) Page Components

```
AskPage
├── QuerySection
│   ├── SectionHeader ("Ask about your campaigns")
│   ├── QueryInput
│   │   ├── TextArea
│   │   ├── SuggestedQueries (chips)
│   │   │   ├── "Why did Google Search increase?"
│   │   │   ├── "Show ROAS trends"
│   │   │   └── "Compare Meta vs Google"
│   │   └── SubmitButton
│   └── CampaignSelector (optional filter)
│
├── ResponseSection
│   ├── LoadingIndicator
│   ├── ResponseCard
│   │   ├── QueryText (what was asked)
│   │   ├── ResponseText (LLM answer)
│   │   ├── SupportingData
│   │   │   ├── MiniChart (if applicable)
│   │   │   └── DataTable (if applicable)
│   │   ├── SourcesUsed (tools called)
│   │   └── FeedbackButtons (👍/👎)
│   └── FollowUpSuggestions
│
└── QueryHistory
    ├── SectionHeader ("Recent Queries")
    └── QueryHistoryList
        └── QueryHistoryItem[]
            ├── Timestamp
            ├── QueryText (truncated)
            └── ExpandButton
```

### 2.5 Recommendations Page Components

```
RecommendationsPage
├── TabBar
│   ├── Tab (Pending) [count badge]
│   ├── Tab (Applied)
│   └── Tab (Rejected)
│
├── RecommendationsList
│   └── RecommendationCard[]
│       ├── Header
│       │   ├── TypeIcon
│       │   ├── Title
│       │   ├── ConfidenceScore
│       │   └── Timestamp
│       ├── Body
│       │   ├── Description
│       │   ├── ImpactPreview
│       │   │   ├── CurrentState
│       │   │   └── ProposedState
│       │   └── ExplanationText
│       ├── Actions (for pending)
│       │   ├── ApproveButton
│       │   ├── RejectButton
│       │   └── ModifyButton
│       └── Footer
│           ├── CampaignLink
│           └── ViewDetailsLink
│
└── BulkActions (for pending)
    ├── SelectAll
    ├── ApproveSelected
    └── RejectSelected
```

### 2.6 Optimizer Status Page Components

```
OptimizerPage
├── StatusHeader
│   ├── StatusIndicator (🟢 Running / 🟡 Paused / 🔴 Error)
│   ├── LastRunTime
│   ├── NextRunTime
│   └── ActionButtons
│       ├── PauseAllButton
│       └── ForceRunButton
│
├── StatsOverview
│   ├── MetricCard (Campaigns Optimizing)
│   ├── MetricCard (Total Optimizations Today)
│   ├── MetricCard (Avg Optimization Time)
│   └── MetricCard (Error Rate)
│
├── DecisionLogSection
│   ├── SectionHeader ("Recent Decisions")
│   ├── FilterBar
│   │   ├── CampaignFilter
│   │   ├── TypeFilter (allocation/pause/etc)
│   │   └── DateFilter
│   └── DecisionTimeline
│       └── DecisionCard[]
│           ├── Timestamp
│           ├── CampaignName
│           ├── DecisionType
│           ├── Description
│           ├── Reasoning
│           └── ImpactMetrics
│
└── FactorAttributionSection
    ├── SectionHeader ("What's Driving Decisions")
    └── FactorChart (horizontal bar)
        ├── Seasonality
        ├── Performance (ROAS)
        ├── Risk Adjustment
        ├── Carryover Effect
        └── Competition
```

---

## 3. Integration Points

### 3.1 Backend API Endpoints Needed

```python
# Campaign endpoints
GET  /api/campaigns                    # List all campaigns
GET  /api/campaigns/{id}               # Get campaign details
GET  /api/campaigns/{id}/metrics       # Get campaign metrics (time range)
GET  /api/campaigns/{id}/allocation    # Current allocation
GET  /api/campaigns/{id}/arms          # List arms with performance
POST /api/campaigns/{id}/pause         # Pause campaign
POST /api/campaigns/{id}/resume        # Resume campaign

# Optimizer endpoints
GET  /api/optimizer/status             # Service status
GET  /api/optimizer/decisions          # Decision log
GET  /api/optimizer/factors            # Factor attribution
POST /api/optimizer/force-run          # Force optimization cycle

# Explanation endpoints
GET  /api/changes                      # Allocation change history
GET  /api/changes/{id}/explain         # Get explanation for change
GET  /api/explanations/performance     # Explain performance

# Query endpoints
POST /api/query                        # Natural language query
GET  /api/query/history                # Query history

# Recommendation endpoints
GET  /api/recommendations              # List recommendations
POST /api/recommendations/{id}/approve # Approve recommendation
POST /api/recommendations/{id}/reject  # Reject recommendation
POST /api/recommendations/{id}/modify  # Modify and approve

# User endpoints
GET  /api/user/me                      # Current user
GET  /api/user/preferences             # User preferences
```

### 3.2 Real-time Updates

```
WebSocket /ws/updates
├── Event: campaign_status_changed
├── Event: optimization_completed
├── Event: new_recommendation
├── Event: alert_triggered
└── Event: allocation_changed
```

### 3.3 Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  Frontend   │────▶│  FastAPI    │────▶│  Orchestrator   │
│  (React)    │◀────│  Backend    │◀────│  (LLM + MCP)    │
└─────────────┘     └─────────────┘     └─────────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────────┐
                    │  Database   │     │  External APIs  │
                    │  (SQLite)   │     │  (Anthropic,    │
                    └─────────────┘     │   Tavily, etc)  │
                                        └─────────────────┘
```

---

## 4. Color Palette & Design System

Based on Mixpanel inspiration with our own identity:

### Colors

```css
/* Primary */
--primary-500: #7C3AED;      /* Violet - main accent */
--primary-600: #6D28D9;      /* Violet - hover */
--primary-100: #EDE9FE;      /* Violet - light bg */

/* Neutral */
--gray-50: #FAFAFA;          /* Page background */
--gray-100: #F5F5F5;         /* Card background */
--gray-200: #E5E5E5;         /* Borders */
--gray-500: #737373;         /* Secondary text */
--gray-900: #171717;         /* Primary text */

/* Semantic */
--success: #22C55E;          /* Green - positive */
--warning: #F59E0B;          /* Amber - warning */
--error: #EF4444;            /* Red - error */
--info: #3B82F6;             /* Blue - info */

/* Platform Colors */
--google: #4285F4;
--meta: #1877F2;
--trade-desk: #00A98F;
```

### Typography

```css
/* Font Family */
--font-sans: 'Inter', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', monospace;

/* Sizes */
--text-xs: 0.75rem;          /* 12px */
--text-sm: 0.875rem;         /* 14px */
--text-base: 1rem;           /* 16px */
--text-lg: 1.125rem;         /* 18px */
--text-xl: 1.25rem;          /* 20px */
--text-2xl: 1.5rem;          /* 24px */
--text-3xl: 1.875rem;        /* 30px */
```

### Spacing

```css
--space-1: 0.25rem;          /* 4px */
--space-2: 0.5rem;           /* 8px */
--space-3: 0.75rem;          /* 12px */
--space-4: 1rem;             /* 16px */
--space-6: 1.5rem;           /* 24px */
--space-8: 2rem;             /* 32px */
```

---

## 5. Key UI Patterns

### 5.1 Metric Card Pattern
```
┌─────────────────────────────────┐
│  Total Spend                    │
│  $12,450.00          ▲ 12.5%   │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁ (sparkline)  │
└─────────────────────────────────┘
```

### 5.2 Allocation Display Pattern
```
┌─────────────────────────────────────────────┐
│  Google Search    ████████████░░░ 35%  +5%  │
│  Meta Display     ███████░░░░░░░░ 25%  -2%  │
│  Trade Desk       ██████░░░░░░░░░ 20%   0%  │
│  Other            ████░░░░░░░░░░░ 20%  -3%  │
└─────────────────────────────────────────────┘
```

### 5.3 Explanation Card Pattern
```
┌─────────────────────────────────────────────┐
│  Why did Google Search increase by 20%?     │
├─────────────────────────────────────────────┤
│  The Google Search budget increased due to: │
│                                             │
│  • Q4 Seasonality Effect (+12%)             │
│  • Strong ROAS improvement (2.1 → 2.5)      │
│  • Reduced risk score (0.15 → 0.10)         │
│                                             │
│  ─────────────────────────────────────────  │
│  📅 Jan 31, 2026 at 2:45 PM                 │
│  🤖 Generated by Claude                     │
└─────────────────────────────────────────────┘
```

### 5.4 Recommendation Card Pattern
```
┌─────────────────────────────────────────────┐
│  🎯 Increase Google Search Allocation       │
│     Confidence: ████████░░ 85%              │
├─────────────────────────────────────────────┤
│  Current: 25%  →  Suggested: 35%            │
│                                             │
│  Expected impact: +12% ROAS                 │
│                                             │
│  Based on strong recent performance...      │
│  [Read more]                                │
├─────────────────────────────────────────────┤
│  [✓ Approve]  [✗ Reject]  [✎ Modify]       │
└─────────────────────────────────────────────┘
```

---

## 6. File Structure (React + FastAPI)

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── PageLayout.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── common/
│   │   │   ├── MetricCard.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   ├── TimeRangeSelector.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── charts/
│   │   │   ├── TimeSeriesChart.tsx
│   │   │   ├── AllocationPieChart.tsx
│   │   │   ├── BarChart.tsx
│   │   │   ├── Sparkline.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── campaigns/
│   │   │   ├── CampaignCard.tsx
│   │   │   ├── CampaignTable.tsx
│   │   │   ├── AllocationTable.tsx
│   │   │   ├── ArmCard.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── explanations/
│   │   │   ├── ExplanationCard.tsx
│   │   │   ├── FactorList.tsx
│   │   │   ├── ChangeTimeline.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── recommendations/
│   │   │   ├── RecommendationCard.tsx
│   │   │   ├── ApprovalActions.tsx
│   │   │   └── index.ts
│   │   │
│   │   └── query/
│   │       ├── QueryInput.tsx
│   │       ├── QueryResponse.tsx
│   │       ├── QueryHistory.tsx
│   │       └── index.ts
│   │
│   ├── pages/
│   │   ├── HomePage.tsx
│   │   ├── CampaignsPage.tsx
│   │   ├── CampaignDetailPage.tsx
│   │   ├── OptimizerPage.tsx
│   │   ├── AskPage.tsx
│   │   ├── RecommendationsPage.tsx
│   │   └── SettingsPage.tsx
│   │
│   ├── hooks/
│   │   ├── useCampaigns.ts
│   │   ├── useMetrics.ts
│   │   ├── useRecommendations.ts
│   │   ├── useQuery.ts
│   │   └── useWebSocket.ts
│   │
│   ├── services/
│   │   ├── api.ts
│   │   ├── websocket.ts
│   │   └── auth.ts
│   │
│   ├── stores/
│   │   ├── campaignStore.ts
│   │   ├── uiStore.ts
│   │   └── userStore.ts
│   │
│   └── types/
│       ├── campaign.ts
│       ├── metrics.ts
│       ├── recommendation.ts
│       └── index.ts
│
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js

backend/
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── routes/
│   │   ├── campaigns.py
│   │   ├── optimizer.py
│   │   ├── explanations.py
│   │   ├── query.py
│   │   ├── recommendations.py
│   │   └── auth.py
│   ├── schemas/
│   │   ├── campaign.py
│   │   ├── metrics.py
│   │   └── recommendation.py
│   └── dependencies.py
└── requirements.txt
```

---

## 7. Potential Challenges

### 7.1 Technical Challenges

| Challenge | Mitigation |
|-----------|------------|
| **LLM Response Latency** | Show loading states, stream responses, cache common queries |
| **Real-time Updates** | WebSocket with fallback to polling, optimistic UI updates |
| **Large Data Volumes** | Pagination, virtualized lists, time range limits |
| **Chart Performance** | Use Canvas-based charts (Recharts), limit data points |
| **Authentication State** | JWT with refresh tokens, persistent storage |

### 7.2 UX Challenges

| Challenge | Mitigation |
|-----------|------------|
| **Complex Explanations** | Progressive disclosure, "Read more" expansion |
| **Information Overload** | Sensible defaults, collapsible sections |
| **Query Ambiguity** | Suggested queries, clarification prompts |
| **Approval Workflow** | Clear status indicators, undo capability |

### 7.3 Integration Challenges

| Challenge | Mitigation |
|-----------|------------|
| **Backend API Changes** | Versioned API, TypeScript types from OpenAPI |
| **Optional Dependencies** | Graceful degradation (no LLM = template explanations) |
| **Database Schema Changes** | Migrations, backwards compatibility |

---

## 8. Development Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up React project with Vite + TypeScript
- [ ] Configure Tailwind CSS with design system
- [ ] Create FastAPI backend with basic routes
- [ ] Build layout components (Sidebar, TopBar, PageLayout)
- [ ] Implement basic routing

### Phase 2: Core Pages (Week 2)
- [ ] Home page with metric cards
- [ ] Campaigns list page
- [ ] Campaign detail page (basic)
- [ ] API integration for campaigns and metrics

### Phase 3: Visualizations (Week 3)
- [ ] Time series charts
- [ ] Allocation pie chart
- [ ] Performance comparison charts
- [ ] Sparklines in metric cards

### Phase 4: Interpretability Features (Week 4)
- [ ] Explanation cards and display
- [ ] Decision log / timeline
- [ ] Factor attribution visualization
- [ ] Change history view

### Phase 5: Interactive Features (Week 5)
- [ ] Natural language query interface
- [ ] Recommendations approval workflow
- [ ] Override suggestion flow
- [ ] Real-time updates (WebSocket)

### Phase 6: Polish (Week 6)
- [ ] Loading states and skeletons
- [ ] Error handling and empty states
- [ ] Responsive design
- [ ] Performance optimization
- [ ] Testing

---

## 9. Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS
- **Charts**: Recharts (or Apache ECharts)
- **State**: Zustand (lightweight) or React Query
- **Routing**: React Router v6
- **HTTP**: Axios or fetch
- **WebSocket**: socket.io-client

### Backend API
- **Framework**: FastAPI
- **Validation**: Pydantic
- **ORM**: SQLAlchemy (already have)
- **Auth**: JWT tokens
- **WebSocket**: FastAPI WebSocket

### Development
- **Package Manager**: pnpm (faster than npm)
- **Linting**: ESLint + Prettier
- **Testing**: Vitest + React Testing Library

---

## 10. Wireframes (ASCII)

### Home Page
```
┌─────────────────────────────────────────────────────────────────────────┐
│ [≡] Ads Optimizer                              🔍 Search    👤 User   │
├────────────┬────────────────────────────────────────────────────────────┤
│            │                                                            │
│  🏠 Home   │  Good Morning, Komal                                      │
│            │                                                            │
│  📊 Camp.  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│            │  │ $12,450  │ │  2.45    │ │    5     │ │    3     │     │
│  🤖 Optim. │  │ Spend    │ │ ROAS     │ │ Campaigns│ │ Pending  │     │
│            │  │ ▲ 12.5%  │ │ ▲ 5.2%   │ │          │ │ Recs     │     │
│  💬 Ask    │  │ ▁▂▃▄▅▆▇█ │ │ ▁▂▃▄▅▆▇█ │ │          │ │          │     │
│            │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│  ✓ Recs    │                                                            │
│            │  Your Campaigns                                            │
│  ⚠ Alerts  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│            │  │ Campaign1│ │ Campaign2│ │ Campaign3│                   │
│  ──────    │  │ 🟢 Active│ │ 🟡 Paused│ │ 🟢 Active│                   │
│            │  │ $5,200   │ │ $3,100   │ │ $4,150   │                   │
│  📌 Pinned │  └──────────┘ └──────────┘ └──────────┘                   │
│  • Camp 1  │                                                            │
│  • Camp 2  │  Recent Decisions                    Pending Recommendations│
│            │  ┌────────────────────────┐         ┌────────────────────┐ │
│  ──────    │  │ 10:30 Google +20%     │         │ Increase Meta...   │ │
│            │  │ 09:15 Meta -5%        │         │ [Approve] [Reject] │ │
│  ⚙ Settings│  │ 08:00 Optimization... │         └────────────────────┘ │
│            │  └────────────────────────┘                                │
└────────────┴────────────────────────────────────────────────────────────┘
```

### Campaign Detail Page
```
┌─────────────────────────────────────────────────────────────────────────┐
│ [≡] Ads Optimizer                              🔍 Search    👤 User   │
├────────────┬────────────────────────────────────────────────────────────┤
│            │  Campaign: Q1 Brand Awareness              [Pause] [Edit] │
│  🏠 Home   │  🟢 Active                                                │
│            │                                                            │
│  📊 Camp.  │  [7D] [30D] [3M] [Custom]                     Compare ☐  │
│    ▶ Camp1 │                                                            │
│    ▶ Camp2 │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│            │  │  2.45   │ │ $5,200  │ │ $12,740 │ │   523   │        │
│  🤖 Optim. │  │  ROAS   │ │  Spend  │ │ Revenue │ │  Conv.  │        │
│            │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│  💬 Ask    │                                                            │
│            │  Performance Over Time                                     │
│  ✓ Recs    │  ┌────────────────────────────────────────────────────┐   │
│            │  │                                              ●      │   │
│  ⚠ Alerts  │  │                                         ●          │   │
│            │  │                                    ●                │   │
│            │  │         ●    ●    ●    ●    ●                       │   │
│            │  │    ●                                                │   │
│            │  └────────────────────────────────────────────────────┘   │
│            │   Jan 24   Jan 25   Jan 26   Jan 27   Jan 28   Jan 29     │
│            │                                                            │
│            │  Budget Allocation              Why These Allocations?    │
│            │  ┌──────────────────┐          ┌────────────────────────┐ │
│            │  │    [PIE CHART]   │          │ Google Search increased │ │
│            │  │                  │          │ by 20% due to:          │ │
│            │  │  Google    35%   │          │ • Q4 Seasonality (+12%) │ │
│            │  │  Meta      25%   │          │ • Strong ROAS (2.1→2.5) │ │
│            │  │  TTD       20%   │          │ • Low risk score        │ │
│            │  │  Other     20%   │          └────────────────────────┘ │
│            │  └──────────────────┘                                      │
└────────────┴────────────────────────────────────────────────────────────┘
```

### Ask Page
```
┌─────────────────────────────────────────────────────────────────────────┐
│ [≡] Ads Optimizer                              🔍 Search    👤 User   │
├────────────┬────────────────────────────────────────────────────────────┤
│            │                                                            │
│  🏠 Home   │  Ask about your campaigns                                 │
│            │                                                            │
│  📊 Camp.  │  ┌────────────────────────────────────────────────────┐   │
│            │  │ Why did Google Search budget increase last week?   │   │
│  🤖 Optim. │  │                                              [Ask] │   │
│            │  └────────────────────────────────────────────────────┘   │
│  💬 Ask ◀  │                                                            │
│            │  Suggestions:                                              │
│  ✓ Recs    │  [Compare Google vs Meta] [Show ROAS trends] [Explain..]  │
│            │                                                            │
│  ⚠ Alerts  │  ┌────────────────────────────────────────────────────┐   │
│            │  │ 🤖 Response                                        │   │
│            │  │                                                    │   │
│            │  │ The Google Search budget increased by 20% (from    │   │
│            │  │ 15% to 35%) due to several converging factors:     │   │
│            │  │                                                    │   │
│            │  │ 1. **Q4 Seasonality**: We're in Q4, which         │   │
│            │  │    historically increases Search performance...    │   │
│            │  │                                                    │   │
│            │  │ 2. **Strong ROAS**: ROAS improved from 2.1 to 2.5 │   │
│            │  │                                                    │   │
│            │  │ [Show Chart]  [View Changes]                       │   │
│            │  │                                                    │   │
│            │  │ 👍 Helpful   👎 Not helpful                        │   │
│            │  └────────────────────────────────────────────────────┘   │
│            │                                                            │
│            │  Recent Queries                                            │
│            │  • "Show ROAS for last month" - 2h ago                    │
│            │  • "Why is Meta underperforming?" - Yesterday             │
└────────────┴────────────────────────────────────────────────────────────┘
```

---

## 11. Next Steps

1. **Confirm technology choice** (React or Streamlit)
2. **Set up project scaffolding**
3. **Build design system components**
4. **Create FastAPI backend routes**
5. **Implement page by page**

---

*Blueprint Version: 1.0*
*Created: January 31, 2026*
