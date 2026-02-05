# Future Enhancements - Detailed Plan

## Overview

This document outlines the detailed changes needed for three major enhancements:
1. Learning Period Detection
2. MMM-Lite Insights Integration
3. Optimizer/Recommendations Improvements

---

## 1. Learning Period Detection

### Current State
- Dual-axis charts have placeholder for learning periods
- No automatic detection of test/learning phases
- No exclusion of learning periods from performance calculations

### Proposed Changes

#### A. Database/Model Changes
**Files to Modify:**
- `src/bandit_ads/database.py`

**Changes:**
- Add `learning_periods` table (optional, or calculate on-the-fly):
  ```python
  class LearningPeriod(Base):
      id = Column(Integer, primary_key=True)
      campaign_id = Column(Integer, ForeignKey('campaigns.id'))
      arm_id = Column(Integer, ForeignKey('arms.id'), nullable=True)  # None = campaign-level
      start_date = Column(DateTime)
      end_date = Column(DateTime)
      reason = Column(String)  # "initial_test", "bid_change", "creative_test", etc.
      status = Column(String)  # "active", "completed"
  ```
- OR calculate dynamically based on:
  - AgentState trials count (< threshold = learning)
  - Time since campaign/arm start (< X days)
  - Alpha/Beta values (high uncertainty = learning)

#### B. API Changes
**Files to Modify:**
- `src/bandit_ads/api/routes/campaigns.py`

**New Endpoints:**
- `GET /api/campaigns/{id}/learning-periods` - Get learning periods for campaign
- `GET /api/campaigns/{id}/time-series` - Add `exclude_learning` query param

**Logic to Add:**
```python
def detect_learning_periods(campaign_id, arm_id=None):
    """
    Detect learning periods based on:
    1. Trials count < learning_threshold (e.g., 1000 impressions)
    2. Days since start < learning_days (e.g., 7 days)
    3. High uncertainty (alpha + beta < threshold)
    """
    # Check agent state
    # Check time since start
    # Return list of {start, end, reason}
```

#### C. Frontend Changes
**Files to Modify:**
- `frontend/components/dual_axis_chart.py`
- `frontend/pages/campaign_detail.py`

**Changes:**
1. **Chart Component:**
   - Accept learning periods list
   - Shade regions on chart (already has structure)
   - Add legend for learning periods
   - Option to exclude learning periods from calculations

2. **Campaign Detail Page:**
   - Fetch learning periods from API
   - Pass to chart component
   - Add toggle: "Exclude learning periods from metrics"
   - Show learning period info box

3. **Visual Indicators:**
   - Shaded background on chart
   - Tooltip on hover: "Learning Period: [reason]"
   - Different color for different reasons

#### D. Data Service Changes
**Files to Modify:**
- `frontend/services/data_service.py`

**New Methods:**
```python
def get_learning_periods(campaign_id, arm_id=None):
    """Get learning periods for campaign/arm"""
    
def get_performance_time_series(campaign_id, time_range, exclude_learning=False):
    """Get time series with option to exclude learning periods"""
```

### Estimated Effort
- **Backend Logic:** 4-6 hours
- **API Endpoints:** 2-3 hours
- **Frontend Integration:** 3-4 hours
- **Testing:** 2-3 hours
- **Total:** 11-16 hours

### Benefits
- More accurate performance metrics
- Clear visualization of test phases
- Better understanding of when data is reliable
- Helps explain performance variations

---

## 2. MMM-Lite Insights Integration

### Current State
- Placeholder structure in campaign detail page
- Shows static example data
- No real MMM analysis integration

### Proposed Changes

#### A. Data Sources
**Options:**
1. **Platform APIs** (Google Ads, Meta, TTD):
   - Audience breakdowns
   - Geographic performance
   - Creative performance
   - Device/placement data

2. **MMM Model Outputs:**
   - Incrementality estimates
   - Attribution factors
   - Carryover effects
   - Competitive effects

3. **Aggregated Metrics:**
   - Calculate from existing metrics
   - Group by audience/geo/creative
   - Compare performance

#### B. Database/Model Changes
**Files to Modify:**
- `src/bandit_ads/database.py` (optional)

**Optional New Tables:**
```python
class AudienceInsight(Base):
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    audience_segment = Column(String)  # "Audience A", "Lookalike 1", etc.
    roas = Column(Float)
    efficiency_delta = Column(Float)  # vs baseline
    impressions = Column(Integer)
    conversions = Column(Integer)

class GeoInsight(Base):
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    geo = Column(String)  # "US", "UK", etc.
    roas = Column(Float)
    efficiency_delta = Column(Float)
    spend = Column(Float)

class CreativeInsight(Base):
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    creative_name = Column(String)
    ctr = Column(Float)
    cvr = Column(Float)
    roas = Column(Float)
    performance_delta = Column(Float)  # vs baseline
```

**OR** Calculate on-the-fly from existing metrics grouped by:
- Arms (creative breakdown)
- Platform entity IDs (audience/geo from platform APIs)

#### C. API Changes
**Files to Modify:**
- `src/bandit_ads/api/routes/campaigns.py`

**New Endpoints:**
- `GET /api/campaigns/{id}/insights/audience` - Audience performance
- `GET /api/campaigns/{id}/insights/geo` - Geographic performance
- `GET /api/campaigns/{id}/insights/creative` - Creative performance
- `GET /api/campaigns/{id}/insights/incrementality` - Incrementality estimates

**Logic to Add:**
```python
def get_audience_insights(campaign_id):
    """
    Get audience breakdown:
    1. Query platform APIs for audience performance
    2. OR aggregate from arms grouped by audience
    3. Calculate efficiency vs baseline
    4. Return top performers
    """

def get_geo_insights(campaign_id):
    """
    Get geographic breakdown:
    1. Query platform APIs for geo performance
    2. OR aggregate from platform entity IDs
    3. Calculate efficiency by region
    """

def get_creative_insights(campaign_id):
    """
    Get creative breakdown:
    1. Group arms by creative
    2. Calculate CTR, CVR, ROAS per creative
    3. Compare to baseline
    """

def get_incrementality_estimates(campaign_id):
    """
    Get incrementality from MMM model:
    1. Query MMM analysis results
    2. Return incrementality % by channel/arm
    3. Include confidence intervals
    """
```

#### D. Frontend Changes
**Files to Modify:**
- `frontend/pages/campaign_detail.py`
- `frontend/services/data_service.py`

**Changes:**
1. **Campaign Detail Page:**
   - Replace placeholder with real API calls
   - Add loading states
   - Add error handling
   - Display top 3-5 insights per category
   - Add "View All" expandable sections

2. **Data Service:**
   ```python
   def get_audience_insights(campaign_id)
   def get_geo_insights(campaign_id)
   def get_creative_insights(campaign_id)
   def get_incrementality_estimates(campaign_id)
   ```

3. **Visual Enhancements:**
   - Bar charts for top performers
   - Color coding (green = above baseline, red = below)
   - Percentage deltas
   - Expandable details

#### E. Platform API Integration
**Files to Modify:**
- `src/bandit_ads/api_connectors.py`

**Changes:**
- Add methods to fetch audience/geo/creative breakdowns:
  ```python
  def get_audience_performance(campaign_id)
  def get_geo_performance(campaign_id)
  def get_creative_performance(campaign_id)
  ```

### Estimated Effort
- **Platform API Integration:** 6-8 hours
- **MMM Model Integration:** 4-6 hours (if MMM exists)
- **API Endpoints:** 3-4 hours
- **Frontend Integration:** 4-5 hours
- **Testing:** 3-4 hours
- **Total:** 20-27 hours

### Benefits
- Real insights instead of placeholders
- Actionable data for optimization
- Better understanding of what's working
- Supports budget reallocation decisions

---

## 3. Optimizer/Recommendations Improvements

### Current State
- Optimizer page shows mock status
- Recommendations page shows mock data
- No real optimization service integration
- No real decision logs
- No real factor attribution

### Proposed Changes

#### A. Optimization Service Integration
**Files to Create/Modify:**
- `src/bandit_ads/optimization_service.py` (new)
- `src/bandit_ads/api/routes/optimizer.py`

**New Service:**
```python
class OptimizationService:
    """
    Continuous optimization service that:
    1. Runs optimization cycles every 15-60 minutes
    2. Maintains agent state in database
    3. Handles multiple campaigns concurrently
    4. Logs all decisions
    5. Generates recommendations
    """
    
    def run_optimization_cycle(self):
        """Run optimization for all active campaigns"""
        
    def optimize_campaign(self, campaign_id):
        """Optimize a single campaign"""
        
    def generate_recommendations(self, campaign_id):
        """Generate recommendations based on optimization"""
        
    def log_decision(self, campaign_id, decision_type, details):
        """Log optimization decision"""
```

#### B. Decision Logging
**Files to Modify:**
- `src/bandit_ads/database.py`

**New Model:**
```python
class OptimizationDecision(Base):
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    arm_id = Column(Integer, ForeignKey('arms.id'), nullable=True)
    decision_type = Column(String)  # "allocation_change", "bid_update", "pause", etc.
    previous_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=True)
    reason = Column(Text)  # Human-readable explanation
    factors = Column(Text)  # JSON: {"factor": "weight"}
    confidence = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # "pending", "applied", "rejected"
```

#### C. Recommendations System
**Files to Modify:**
- `src/bandit_ads/database.py`

**New Model (if not exists):**
```python
class Recommendation(Base):
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    arm_id = Column(Integer, ForeignKey('arms.id'), nullable=True)
    type = Column(String)  # "allocation_change", "budget_adjustment", etc.
    title = Column(String)
    description = Column(Text)
    current_value = Column(Float, nullable=True)
    proposed_value = Column(Float, nullable=True)
    expected_impact = Column(String)
    confidence = Column(Float)
    explanation = Column(Text)
    status = Column(String)  # "pending", "applied", "rejected", "modified"
    created_at = Column(DateTime, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
```

#### D. API Changes
**Files to Modify:**
- `src/bandit_ads/api/routes/optimizer.py`
- `src/bandit_ads/api/routes/recommendations.py`

**Optimizer Endpoints:**
- `GET /api/optimizer/status` - Real status from service
- `GET /api/optimizer/decisions` - Real decision logs
- `GET /api/optimizer/factor-attribution` - Real factor data
- `POST /api/optimizer/pause` - Pause service
- `POST /api/optimizer/resume` - Resume service
- `POST /api/optimizer/force-run` - Trigger optimization

**Recommendations Endpoints:**
- `GET /api/recommendations` - Real recommendations
- `POST /api/recommendations/{id}/approve` - Apply recommendation
- `POST /api/recommendations/{id}/reject` - Reject recommendation
- `POST /api/recommendations/{id}/modify` - Modify recommendation

#### E. Frontend Changes
**Files to Modify:**
- `frontend/pages/optimizer.py`
- `frontend/pages/recommendations.py`
- `frontend/services/data_service.py`

**Optimizer Page:**
- Connect to real optimization service status
- Display real decision logs with filters
- Show real factor attribution
- Add controls for service management

**Recommendations Page:**
- Connect to real recommendations API
- Show real recommendation data
- Working approve/reject actions
- Real-time updates when recommendations change

**Data Service:**
- Update all methods to call real APIs
- Remove mock data fallbacks (or keep as last resort)

#### F. Factor Attribution
**Files to Create/Modify:**
- `src/bandit_ads/explainer.py` (new or existing)

**Logic:**
```python
def explain_decision(decision):
    """
    Generate explanation for optimization decision:
    1. Analyze factors that influenced decision
    2. Calculate attribution weights
    3. Generate human-readable explanation
    4. Return structured explanation
    """
    
def get_factor_attribution(campaign_id, time_range):
    """
    Aggregate factor attribution:
    1. Analyze all decisions in time range
    2. Calculate average factor weights
    3. Return top factors
    """
```

### Estimated Effort
- **Optimization Service:** 8-12 hours
- **Decision Logging:** 4-6 hours
- **Recommendations System:** 6-8 hours
- **Factor Attribution:** 4-6 hours
- **API Integration:** 4-6 hours
- **Frontend Updates:** 4-6 hours
- **Testing:** 4-6 hours
- **Total:** 34-50 hours

### Benefits
- Real optimization running continuously
- Actionable recommendations
- Transparent decision-making
- Better understanding of optimizer behavior
- Production-ready system

---

## Summary Comparison

| Feature | Backend Effort | Frontend Effort | Total Effort | Priority |
|---------|---------------|-----------------|--------------|----------|
| Learning Period Detection | 6-9 hours | 3-4 hours | 11-16 hours | Medium |
| MMM-Lite Insights | 10-14 hours | 4-5 hours | 20-27 hours | Medium |
| Optimizer/Recommendations | 26-38 hours | 4-6 hours | 34-50 hours | High |

## Recommended Order

1. **Learning Period Detection** (11-16 hours)
   - Quickest to implement
   - High visual impact
   - Improves data accuracy

2. **MMM-Lite Insights** (20-27 hours)
   - Medium complexity
   - High value for users
   - Requires platform API integration

3. **Optimizer/Recommendations** (34-50 hours)
   - Most complex
   - Core functionality
   - Requires optimization service

## Dependencies

### Learning Period Detection
- ✅ AgentState model exists
- ✅ Time series data available
- ⚠️ Need detection logic

### MMM-Lite Insights
- ✅ Platform connectors exist
- ⚠️ Need audience/geo/creative API methods
- ⚠️ May need MMM model integration

### Optimizer/Recommendations
- ⚠️ Need optimization service (doesn't exist yet)
- ⚠️ Need decision logging system
- ⚠️ Need recommendations generation

## Questions to Consider

1. **Learning Periods:**
   - What defines a learning period? (trials, time, uncertainty?)
   - Should it be stored or calculated on-the-fly?
   - How long should learning periods be?

2. **MMM Insights:**
   - Do you have an MMM model already?
   - Which platforms provide audience/geo breakdowns?
   - How should incrementality be calculated?

3. **Optimizer/Recommendations:**
   - Is there an optimization service already?
   - How should recommendations be generated?
   - What factors should be tracked?
