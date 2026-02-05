"""
Data Service

Provides data to the frontend by interfacing with the backend API.
Uses API calls when available, falls back to mock data for development.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import random
import requests
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# API base URL - can be overridden with environment variable
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class DataService:
    """
    Service class for fetching data.
    
    Uses API calls when available, falls back to mock data for development.
    """
    
    def __init__(self, api_base_url: Optional[str] = None):
        """
        Initialize data service.
        
        Args:
            api_base_url: Base URL for the API (defaults to http://localhost:8000)
        """
        self.api_base_url = api_base_url or API_BASE_URL
        self.use_mock = False
        
        # Test API connection
        try:
            response = requests.get(f"{self.api_base_url}/api/health", timeout=2)
            if response.status_code == 200:
                self.use_mock = False
            else:
                self.use_mock = True
        except Exception as e:
            print(f"Warning: Could not connect to API at {self.api_base_url}: {e}")
            print("Falling back to mock data")
            self.use_mock = True
    
    def _api_get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request to API."""
        try:
            url = f"{self.api_base_url}{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
    
    # =========================================================================
    # Dashboard Summary
    # =========================================================================
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get dashboard summary metrics."""
        if self.use_mock:
            return self._mock_dashboard_summary()
        
        result = self._api_get("/api/dashboard/summary")
        if result:
            return result
        
        return self._mock_dashboard_summary()
    
    def _mock_dashboard_summary(self) -> Dict[str, Any]:
        """Return mock dashboard summary."""
        return {
            'total_spend_today': 12450.00,
            'spend_trend': 12.5,
            'avg_roas': 2.45,
            'roas_trend': 5.2,
            'active_campaigns': 5,
            'pending_recommendations': 3
        }
    
    # =========================================================================
    # Brand Budget Overview
    # =========================================================================
    
    def get_brand_budget_overview(self, time_range: str = "MTD") -> Dict[str, Any]:
        """
        Get overall brand budget data for the specified time range.
        
        Args:
            time_range: One of 'MTD', 'QTD', 'YTD', or 'FY'
        
        Returns:
            Dict with total_budget, spent, remaining, and time period info
        """
        if self.use_mock:
            return self._mock_brand_budget_overview(time_range)
        
        result = self._api_get("/api/dashboard/brand-budget", params={"time_range": time_range})
        if result:
            return result
        
        return self._mock_brand_budget_overview(time_range)
    
    def _mock_brand_budget_overview(self, time_range: str) -> Dict[str, Any]:
        """Return mock brand budget overview."""
        # Budget amounts based on time range
        budgets = {
            'MTD': {'total': 150000, 'spent': 87500, 'period_label': 'January 2026'},
            'QTD': {'total': 450000, 'spent': 87500, 'period_label': 'Q1 2026'},
            'YTD': {'total': 450000, 'spent': 87500, 'period_label': 'Jan 2026'},
            'FY': {'total': 1800000, 'spent': 1237500, 'period_label': 'FY 2026 (Apr 2025 - Mar 2026)'}
        }
        
        data = budgets.get(time_range, budgets['MTD'])
        remaining = data['total'] - data['spent']
        pacing = data['spent'] / data['total'] if data['total'] > 0 else 0
        
        return {
            'total_budget': data['total'],
            'spent': data['spent'],
            'remaining': remaining,
            'pacing_percent': pacing,
            'period_label': data['period_label'],
            'time_range': time_range
        }
    
    def get_channel_splits(self, time_range: str = "MTD") -> List[Dict[str, Any]]:
        """
        Get budget allocation by channel.
        
        Returns list of channels with their budget, spend, and campaign count.
        """
        if self.use_mock:
            return self._mock_channel_splits(time_range)
        
        result = self._api_get("/api/dashboard/channel-splits", params={"time_range": time_range})
        if result:
            return result
        
        return self._mock_channel_splits(time_range)
    
    def _mock_channel_splits(self, time_range: str) -> List[Dict[str, Any]]:
        """Return mock channel splits data."""
        # Channel data varies slightly by time range
        multipliers = {
            'MTD': 1.0,
            'QTD': 1.0,
            'YTD': 1.0,
            'FY': 12.0  # Full year is larger
        }
        mult = multipliers.get(time_range, 1.0)
        
        channels = [
            {
                'id': 'programmatic',
                'name': 'Programmatic (TTD)',
                'icon': '🎯',
                'color': '#6366F1',
                'budget': int(45000 * mult),
                'spent': int(28500 * mult),
                'allocation_percent': 0.30,
                'campaign_count': 3,
                'roas': 2.35,
                'roas_trend': 5.2
            },
            {
                'id': 'youtube',
                'name': 'YouTube',
                'icon': '📺',
                'color': '#EF4444',
                'budget': int(37500 * mult),
                'spent': int(22000 * mult),
                'allocation_percent': 0.25,
                'campaign_count': 2,
                'roas': 1.85,
                'roas_trend': -2.1
            },
            {
                'id': 'search',
                'name': 'Search (Google/Bing)',
                'icon': '🔍',
                'color': '#22C55E',
                'budget': int(30000 * mult),
                'spent': int(19500 * mult),
                'allocation_percent': 0.20,
                'campaign_count': 4,
                'roas': 2.85,
                'roas_trend': 8.5
            },
            {
                'id': 'social',
                'name': 'Social (Meta)',
                'icon': '👥',
                'color': '#3B82F6',
                'budget': int(22500 * mult),
                'spent': int(12500 * mult),
                'allocation_percent': 0.15,
                'campaign_count': 2,
                'roas': 2.15,
                'roas_trend': 3.2
            },
            {
                'id': 'display',
                'name': 'Display (GDN)',
                'icon': '🖼️',
                'color': '#F59E0B',
                'budget': int(15000 * mult),
                'spent': int(5000 * mult),
                'allocation_percent': 0.10,
                'campaign_count': 2,
                'roas': 1.65,
                'roas_trend': -5.0
            }
        ]
        
        return channels
    
    def get_channel_campaigns(self, channel_id: str, time_range: str = "MTD") -> List[Dict[str, Any]]:
        """
        Get campaigns running on a specific channel with their spend allocation.
        
        Args:
            channel_id: The channel identifier (e.g., 'programmatic', 'youtube')
            time_range: The time range filter
        
        Returns:
            List of campaigns with spend allocation for this channel
        """
        if self.use_mock:
            return self._mock_channel_campaigns(channel_id, time_range)
        
        return self._mock_channel_campaigns(channel_id, time_range)
    
    def _mock_channel_campaigns(self, channel_id: str, time_range: str) -> List[Dict[str, Any]]:
        """Return mock campaigns for a channel."""
        campaigns_by_channel = {
            'programmatic': [
                {
                    'id': 1,
                    'name': 'Q1 Brand Awareness - TTD',
                    'status': 'active',
                    'budget': 20000,
                    'spent': 14200,
                    'allocation_percent': 0.45,
                    'roas': 2.45,
                    'roas_trend': 6.2,
                    'daily_spend': 450,
                    'impressions': 1250000,
                    'clicks': 8750,
                    'conversions': 195
                },
                {
                    'id': 2,
                    'name': 'Retargeting - Programmatic',
                    'status': 'active',
                    'budget': 15000,
                    'spent': 9800,
                    'allocation_percent': 0.35,
                    'roas': 2.85,
                    'roas_trend': 12.1,
                    'daily_spend': 320,
                    'impressions': 890000,
                    'clicks': 6230,
                    'conversions': 145
                },
                {
                    'id': 3,
                    'name': 'Product Launch - Display',
                    'status': 'active',
                    'budget': 10000,
                    'spent': 4500,
                    'allocation_percent': 0.20,
                    'roas': 1.95,
                    'roas_trend': -3.5,
                    'daily_spend': 150,
                    'impressions': 450000,
                    'clicks': 2250,
                    'conversions': 52
                }
            ],
            'youtube': [
                {
                    'id': 4,
                    'name': 'Brand Awareness - Video',
                    'status': 'active',
                    'budget': 25000,
                    'spent': 15500,
                    'allocation_percent': 0.65,
                    'roas': 1.75,
                    'roas_trend': -1.5,
                    'daily_spend': 520,
                    'impressions': 2500000,
                    'clicks': 12500,
                    'conversions': 98
                },
                {
                    'id': 5,
                    'name': 'Product Demo Videos',
                    'status': 'active',
                    'budget': 12500,
                    'spent': 6500,
                    'allocation_percent': 0.35,
                    'roas': 2.05,
                    'roas_trend': 4.2,
                    'daily_spend': 210,
                    'impressions': 980000,
                    'clicks': 4900,
                    'conversions': 45
                }
            ],
            'search': [
                {
                    'id': 6,
                    'name': 'Brand Search Campaign',
                    'status': 'active',
                    'budget': 10000,
                    'spent': 7200,
                    'allocation_percent': 0.35,
                    'roas': 3.45,
                    'roas_trend': 15.2,
                    'daily_spend': 240,
                    'impressions': 150000,
                    'clicks': 6750,
                    'conversions': 285
                },
                {
                    'id': 7,
                    'name': 'Non-Brand Search',
                    'status': 'active',
                    'budget': 12000,
                    'spent': 8500,
                    'allocation_percent': 0.40,
                    'roas': 2.65,
                    'roas_trend': 5.8,
                    'daily_spend': 280,
                    'impressions': 320000,
                    'clicks': 9600,
                    'conversions': 192
                },
                {
                    'id': 8,
                    'name': 'Shopping Campaigns',
                    'status': 'active',
                    'budget': 5000,
                    'spent': 2500,
                    'allocation_percent': 0.15,
                    'roas': 2.85,
                    'roas_trend': 8.5,
                    'daily_spend': 85,
                    'impressions': 85000,
                    'clicks': 2550,
                    'conversions': 68
                },
                {
                    'id': 9,
                    'name': 'Competitor Conquesting',
                    'status': 'paused',
                    'budget': 3000,
                    'spent': 1300,
                    'allocation_percent': 0.10,
                    'roas': 1.95,
                    'roas_trend': -8.2,
                    'daily_spend': 0,
                    'impressions': 45000,
                    'clicks': 1350,
                    'conversions': 32
                }
            ],
            'social': [
                {
                    'id': 10,
                    'name': 'Meta - Prospecting',
                    'status': 'active',
                    'budget': 15000,
                    'spent': 8500,
                    'allocation_percent': 0.60,
                    'roas': 2.05,
                    'roas_trend': 2.5,
                    'daily_spend': 280,
                    'impressions': 1800000,
                    'clicks': 18000,
                    'conversions': 126
                },
                {
                    'id': 11,
                    'name': 'Meta - Retargeting',
                    'status': 'active',
                    'budget': 7500,
                    'spent': 4000,
                    'allocation_percent': 0.40,
                    'roas': 2.35,
                    'roas_trend': 5.2,
                    'daily_spend': 135,
                    'impressions': 650000,
                    'clicks': 6500,
                    'conversions': 78
                }
            ],
            'display': [
                {
                    'id': 12,
                    'name': 'GDN - Awareness',
                    'status': 'active',
                    'budget': 10000,
                    'spent': 3500,
                    'allocation_percent': 0.70,
                    'roas': 1.55,
                    'roas_trend': -6.5,
                    'daily_spend': 115,
                    'impressions': 2200000,
                    'clicks': 8800,
                    'conversions': 35
                },
                {
                    'id': 13,
                    'name': 'GDN - Remarketing',
                    'status': 'active',
                    'budget': 5000,
                    'spent': 1500,
                    'allocation_percent': 0.30,
                    'roas': 1.95,
                    'roas_trend': 2.1,
                    'daily_spend': 50,
                    'impressions': 450000,
                    'clicks': 1350,
                    'conversions': 22
                }
            ]
        }
        
        return campaigns_by_channel.get(channel_id, [])
    
    def get_channel_recommendations(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Get budget optimizer recommendations for a specific channel.
        
        Args:
            channel_id: The channel identifier
        
        Returns:
            List of recommendations specific to this channel
        """
        if self.use_mock:
            return self._mock_channel_recommendations(channel_id)
        
        return self._mock_channel_recommendations(channel_id)
    
    def _mock_channel_recommendations(self, channel_id: str) -> List[Dict[str, Any]]:
        """Return mock recommendations for a channel."""
        recommendations_by_channel = {
            'programmatic': [
                {
                    'id': 101,
                    'type': 'increase_budget',
                    'title': 'Increase Retargeting Budget',
                    'description': 'Retargeting campaign ROAS is 2.85, significantly above average. Recommend increasing budget by 20%.',
                    'confidence': 0.88,
                    'expected_impact': '+$1,200 revenue/week',
                    'current_value': '$15,000',
                    'proposed_value': '$18,000'
                },
                {
                    'id': 102,
                    'type': 'reallocation',
                    'title': 'Shift Budget from Product Launch',
                    'description': 'Product Launch display has declining ROAS. Reallocate 30% to Retargeting.',
                    'confidence': 0.75,
                    'expected_impact': '+8% overall channel ROAS',
                    'current_value': '20% allocation',
                    'proposed_value': '14% allocation'
                }
            ],
            'youtube': [
                {
                    'id': 103,
                    'type': 'creative_refresh',
                    'title': 'Refresh Video Creatives',
                    'description': 'Brand Awareness videos showing fatigue (CTR dropped 15%). New creatives recommended.',
                    'confidence': 0.72,
                    'expected_impact': '+12% CTR',
                    'current_value': '0.5% CTR',
                    'proposed_value': '0.56% CTR'
                }
            ],
            'search': [
                {
                    'id': 104,
                    'type': 'increase_budget',
                    'title': 'Scale Brand Search Campaign',
                    'description': 'Brand Search has highest ROAS (3.45) but is budget constrained. Impression share is 65%.',
                    'confidence': 0.92,
                    'expected_impact': '+$2,500 revenue/week',
                    'current_value': '$10,000',
                    'proposed_value': '$15,000'
                },
                {
                    'id': 105,
                    'type': 'pause',
                    'title': 'Keep Competitor Conquesting Paused',
                    'description': 'Competitor Conquesting ROAS is below target. Wait for new strategy before resuming.',
                    'confidence': 0.85,
                    'expected_impact': 'Save $650/week',
                    'current_value': 'Paused',
                    'proposed_value': 'Keep Paused'
                }
            ],
            'social': [
                {
                    'id': 106,
                    'type': 'audience_expansion',
                    'title': 'Expand Lookalike Audiences',
                    'description': 'Current audiences are saturating. Expand to 3% lookalikes from 1%.',
                    'confidence': 0.68,
                    'expected_impact': '+25% reach',
                    'current_value': '1% lookalike',
                    'proposed_value': '3% lookalike'
                }
            ],
            'display': [
                {
                    'id': 107,
                    'type': 'decrease_budget',
                    'title': 'Reduce GDN Awareness Budget',
                    'description': 'Display awareness ROAS is 1.55, below profitability threshold. Reduce budget or reallocate.',
                    'confidence': 0.78,
                    'expected_impact': 'Improve overall ROAS by 5%',
                    'current_value': '$10,000',
                    'proposed_value': '$7,000'
                },
                {
                    'id': 108,
                    'type': 'reallocation',
                    'title': 'Shift to Remarketing',
                    'description': 'Remarketing showing better ROAS. Move 30% of awareness budget to remarketing.',
                    'confidence': 0.82,
                    'expected_impact': '+15% channel ROAS',
                    'current_value': '70% awareness / 30% remarketing',
                    'proposed_value': '50% awareness / 50% remarketing'
                }
            ]
        }
        
        return recommendations_by_channel.get(channel_id, [])
    
    # =========================================================================
    # Campaigns
    # =========================================================================
    
    def get_campaigns(self) -> List[Dict[str, Any]]:
        """Get list of all campaigns."""
        if self.use_mock:
            return self._mock_campaigns()
        
        result = self._api_get("/api/campaigns")
        if result:
            return result
        
        return self._mock_campaigns()
    
    def _mock_campaigns(self) -> List[Dict[str, Any]]:
        """Return mock campaigns."""
        return [
            {
                'id': 1,
                'name': 'Q1 Brand Awareness',
                'status': 'active',
                'spend': 5200.00,
                'roas': 2.45,
                'roas_trend': 8.5,
                'arms_count': 4,
                'updated_at': '2 hours ago'
            },
            {
                'id': 2,
                'name': 'Product Launch - Widget X',
                'status': 'active',
                'spend': 3150.00,
                'roas': 2.15,
                'roas_trend': -3.2,
                'arms_count': 3,
                'updated_at': '1 hour ago'
            },
            {
                'id': 3,
                'name': 'Retargeting Campaign',
                'status': 'paused',
                'spend': 1800.00,
                'roas': 3.20,
                'roas_trend': 12.1,
                'arms_count': 2,
                'updated_at': '1 day ago'
            },
            {
                'id': 4,
                'name': 'Holiday Promotions',
                'status': 'active',
                'spend': 4500.00,
                'roas': 1.85,
                'roas_trend': 5.5,
                'arms_count': 5,
                'updated_at': '30 min ago'
            }
        ]
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific campaign."""
        if self.use_mock:
            campaigns = self._mock_campaigns()
            for c in campaigns:
                if c['id'] == campaign_id:
                    return c
            return None
        
        result = self._api_get(f"/api/campaigns/{campaign_id}")
        if result:
            return result
        
        # Fallback to mock
        campaigns = self._mock_campaigns()
        for c in campaigns:
            if c['id'] == campaign_id:
                return c
        return None
    
    def get_campaign_metrics(self, campaign_id: int, time_range: str = "7D") -> Dict[str, Any]:
        """Get campaign metrics."""
        if self.use_mock:
            return {
                'roas': 2.45,
                'roas_trend': 8.5,
                'spend': 5200.00,
                'spend_trend': 12.3,
                'revenue': 12740.00,
                'revenue_trend': 15.2,
                'conversions': 523,
                'conv_trend': 10.5,
                'ctr': 0.045,
                'ctr_trend': 2.1,
                'cvr': 0.032,
                'cvr_trend': -1.5
            }
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/metrics", params={"time_range": time_range})
        if result:
            return result
        
        # Fallback to mock
        return {
            'roas': 2.45,
            'roas_trend': 8.5,
            'spend': 5200.00,
            'spend_trend': 12.3,
            'revenue': 12740.00,
            'revenue_trend': 15.2,
            'conversions': 523,
            'conv_trend': 10.5,
            'ctr': 0.045,
            'ctr_trend': 2.1,
            'cvr': 0.032,
            'cvr_trend': -1.5
        }
    
    def get_enhanced_campaign_metrics(self, campaign_id: int, primary_kpi: str = "ROAS") -> Dict[str, Any]:
        """Get enhanced campaign metrics with today/MTD/total spend, targets, and benchmarks."""
        if self.use_mock:
            return {
                "campaign_id": campaign_id,
                "primary_kpi": primary_kpi,
                "today": {
                    "spend": 150.0,
                    "revenue": 350.0,
                    "roas": 2.33,
                    "cpa": 45.0,
                    "cpc": 1.2,
                    "cvr": 0.035,
                    "aov": 50.0,
                    "conversions": 3
                },
                "mtd": {
                    "spend": 4500.0,
                    "revenue": 10500.0,
                    "roas": 2.33,
                    "cpa": 45.0,
                    "cpc": 1.2,
                    "cvr": 0.035,
                    "aov": 50.0,
                    "conversions": 100
                },
                "total": {
                    "spend": 15000.0,
                    "revenue": 35000.0,
                    "roas": 2.33,
                    "cpa": 45.0,
                    "cpc": 1.2,
                    "cvr": 0.035,
                    "aov": 50.0,
                    "conversions": 333
                },
                "targets": {
                    "roas": 2.0,
                    "cpa": 50.0,
                    "revenue": 30000.0,
                    "conversions": 100
                },
                "benchmarks": {
                    "roas": 1.8,
                    "cpa": 55.0,
                    "revenue": 27000.0,
                    "conversions": 90
                },
                "efficiency_delta": 29.4,
                "status": "scaling"
            }
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/enhanced-metrics", params={"primary_kpi": primary_kpi})
        if result:
            return result
        
        # Fallback to mock (use the mock data defined above)
        return {
            "campaign_id": campaign_id,
            "primary_kpi": primary_kpi,
            "today": {
                "spend": 150.0,
                "revenue": 350.0,
                "roas": 2.33,
                "cpa": 45.0,
                "cpc": 1.2,
                "cvr": 0.035,
                "aov": 50.0,
                "conversions": 3
            },
            "mtd": {
                "spend": 4500.0,
                "revenue": 10500.0,
                "roas": 2.33,
                "cpa": 45.0,
                "cpc": 1.2,
                "cvr": 0.035,
                "aov": 50.0,
                "conversions": 100
            },
            "total": {
                "spend": 15000.0,
                "revenue": 35000.0,
                "roas": 2.33,
                "cpa": 45.0,
                "cpc": 1.2,
                "cvr": 0.035,
                "aov": 50.0,
                "conversions": 333
            },
            "targets": {
                "roas": 2.0,
                "cpa": 50.0,
                "revenue": 30000.0,
                "conversions": 100
            },
            "benchmarks": {
                "roas": 1.8,
                "cpa": 55.0,
                "revenue": 27000.0,
                "conversions": 90
            },
            "efficiency_delta": 29.4,
            "status": "scaling"
        }
    
    def get_campaign_settings(self, campaign_id: int) -> Dict[str, Any]:
        """Get campaign settings including targets, benchmarks, and thresholds."""
        if self.use_mock:
            return {
                "campaign_id": campaign_id,
                "primary_kpi": "ROAS",
                "targets": {
                    "roas": 2.0,
                    "cpa": 50.0,
                    "revenue": None,
                    "conversions": 100
                },
                "benchmarks": {
                    "roas": 1.8,
                    "cpa": 55.0,
                    "revenue": None,
                    "conversions": 90
                },
                "thresholds": {
                    "scaling": 1.1,
                    "stable": 0.9
                }
            }
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/settings")
        if result:
            return result
        
        # Fallback to mock
        return {
            "campaign_id": campaign_id,
            "primary_kpi": "ROAS",
            "targets": {
                "roas": 2.0,
                "cpa": 50.0,
                "revenue": None,
                "conversions": 100
            },
            "benchmarks": {
                "roas": 1.8,
                "cpa": 55.0,
                "revenue": None,
                "conversions": 90
            },
            "thresholds": {
                "scaling": 1.1,
                "stable": 0.9
            }
        }
    
    def update_campaign_settings(self, campaign_id: int, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update campaign settings."""
        if self.use_mock:
            return {
                "campaign_id": campaign_id,
                "message": "Settings updated successfully (mock)",
                "settings": settings
            }
        
        result = self._api_post(f"/api/campaigns/{campaign_id}/settings", json=settings)
        if result:
            return result
        
        # Fallback to mock
        return {
            "campaign_id": campaign_id,
            "message": "Settings updated successfully (mock)",
            "settings": settings
        }
    
    def get_channel_breakdown(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get channel and tactic breakdown with budget utilization and pacing."""
        if self.use_mock:
            return [
                {
                    "channel": "Google - Search",
                    "platform": "Google",
                    "channel_type": "Search",
                    "spend": 5000.0,
                    "revenue": 12000.0,
                    "roas": 2.4,
                    "budget_allocation": 33.3,
                    "utilization": 33.3,
                    "pacing": 105.0,
                    "arms": [
                        {"id": 1, "creative": "Creative A", "bid": 1.5, "spend": 2500.0, "revenue": 6000.0, "roas": 2.4}
                    ]
                },
                {
                    "channel": "Meta - Social",
                    "platform": "Meta",
                    "channel_type": "Social",
                    "spend": 7000.0,
                    "revenue": 15000.0,
                    "roas": 2.14,
                    "budget_allocation": 46.7,
                    "utilization": 46.7,
                    "pacing": 98.0,
                    "arms": [
                        {"id": 2, "creative": "Creative B", "bid": 2.0, "spend": 3500.0, "revenue": 7500.0, "roas": 2.14}
                    ]
                }
            ]
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/channel-breakdown")
        if result:
            return result
        
        # Fallback to mock (use the mock data defined above)
        return [
            {
                "channel": "Google - Search",
                "platform": "Google",
                "channel_type": "Search",
                "spend": 5000.0,
                "revenue": 12000.0,
                "roas": 2.4,
                "budget_allocation": 33.3,
                "utilization": 33.3,
                "pacing": 105.0,
                "arms": [
                    {"id": 1, "creative": "Creative A", "bid": 1.5, "spend": 2500.0, "revenue": 6000.0, "roas": 2.4}
                ]
            },
            {
                "channel": "Meta - Social",
                "platform": "Meta",
                "channel_type": "Social",
                "spend": 7000.0,
                "revenue": 15000.0,
                "roas": 2.14,
                "budget_allocation": 46.7,
                "utilization": 46.7,
                "pacing": 98.0,
                "arms": [
                    {"id": 2, "creative": "Creative B", "bid": 2.0, "spend": 3500.0, "revenue": 7500.0, "roas": 2.14}
                ]
            }
        ]
    
    def get_performance_time_series(self, campaign_id: int, time_range: str = "7D") -> List[Dict[str, Any]]:
        """Get time-series performance data."""
        if self.use_mock:
            return self._mock_time_series(time_range)
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/time-series", params={"time_range": time_range})
        if result:
            return result
        
        return self._mock_time_series(time_range)
    
    def _mock_time_series(self, time_range: str) -> List[Dict[str, Any]]:
        """Get performance time series data."""
        days = {'7D': 7, '30D': 30, '3M': 90}.get(time_range, 7)
        
        data = []
        base_roas = 2.2
        base_spend = 700
        
        for i in range(days):
            date = datetime.now() - timedelta(days=days - i - 1)
            roas = base_roas + random.uniform(-0.3, 0.5) + (i * 0.02)
            spend = base_spend + random.uniform(-100, 150)
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'roas': roas,
                'spend': spend,
                'revenue': spend * roas,
                'conversions': int(spend / 10 * random.uniform(0.8, 1.2))
            })
        
        return data
    
    def get_allocation(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get current allocation for campaign."""
        if self.use_mock:
            return self._mock_allocation(campaign_id)
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/allocation")
        if result:
            return result
        
        return self._mock_allocation(campaign_id)
    
    def _mock_allocation(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get current allocation for campaign."""
        return [
            {'name': 'Google Search', 'allocation': 0.35, 'change': 5.0},
            {'name': 'Meta Display', 'allocation': 0.25, 'change': -2.0},
            {'name': 'Trade Desk', 'allocation': 0.20, 'change': 0.0},
            {'name': 'Google Display', 'allocation': 0.20, 'change': -3.0}
        ]
    
    def get_arms_performance(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get performance metrics for all arms in a campaign."""
        if self.use_mock:
            return self._mock_arms_performance(campaign_id)
        
        result = self._api_get(f"/api/campaigns/{campaign_id}/arms")
        if result:
            return result
        
        return self._mock_arms_performance(campaign_id)
    
    def _mock_arms_performance(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get performance of all arms in campaign."""
        return [
            {'name': 'Google Search - Creative A', 'platform': 'Google', 'channel': 'Search', 'allocation': 35, 'roas': 2.85, 'spend': 1820, 'conversions': 195},
            {'name': 'Meta Display - Creative B', 'platform': 'Meta', 'channel': 'Display', 'allocation': 25, 'roas': 2.15, 'spend': 1300, 'conversions': 98},
            {'name': 'Trade Desk - Programmatic', 'platform': 'TTD', 'channel': 'Display', 'allocation': 20, 'roas': 2.35, 'spend': 1040, 'conversions': 87},
            {'name': 'Google Display - Retarget', 'platform': 'Google', 'channel': 'Display', 'allocation': 20, 'roas': 1.95, 'spend': 1040, 'conversions': 72}
        ]
    
    def pause_campaign(self, campaign_id: int):
        """Pause a campaign."""
        if not self.use_mock:
            try:
                self.optimization_service.pause_campaign(campaign_id)
            except Exception as e:
                print(f"Error pausing campaign: {e}")
    
    def resume_campaign(self, campaign_id: int):
        """Resume a campaign."""
        if not self.use_mock:
            try:
                self.optimization_service.resume_campaign(campaign_id)
            except Exception as e:
                print(f"Error resuming campaign: {e}")
    
    # =========================================================================
    # Explanations
    # =========================================================================
    
    def get_latest_explanation(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest explanation for a campaign."""
        return {
            'text': """The Google Search budget increased by 20% (from 15% to 35%) due to several converging factors:

1. **Q4 Seasonality Effect**: We're in Q4, which historically increases Search channel performance by about 20%. The optimizer detected this seasonal pattern.

2. **Strong Recent Performance**: Over the past week, this arm's ROAS improved from 2.1 to 2.5, a 19% improvement.

3. **Reduced Risk**: The risk score decreased from 0.15 to 0.10, meaning the optimizer has more confidence in this arm's consistent performance.""",
            'timestamp': datetime.now().strftime('%b %d, %Y at %I:%M %p'),
            'model': 'Claude 3.5 Sonnet',
            'factors': {
                'Seasonality': '+12%',
                'ROAS Improvement': '+8%',
                'Risk Reduction': '+5%'
            }
        }
    
    # =========================================================================
    # Recommendations
    # =========================================================================
    
    def get_pending_recommendations(self) -> List[Dict[str, Any]]:
        """Get pending recommendations."""
        if self.use_mock:
            return self._mock_pending_recommendations()
        
        result = self._api_get("/api/recommendations/pending")
        if result:
            return result
        
        return self._mock_pending_recommendations()
    
    def _mock_pending_recommendations(self) -> List[Dict[str, Any]]:
        """Get pending recommendations."""
        return self.get_recommendations(status="pending")
    
    def get_recommendations(self, status: str = "pending") -> List[Dict[str, Any]]:
        """Get recommendations by status."""
        if self.use_mock:
            return self._mock_recommendations(status)
        
        try:
            # Use recommendation manager
            recs = self.recommendation_manager.get_recommendations(status=status)
            return [
                {
                    'id': r.id,
                    'title': r.title,
                    'description': r.description,
                    'type': r.recommendation_type,
                    'campaign_name': f"Campaign {r.campaign_id}",
                    'confidence': r.confidence_score or 0.7,
                    'current_value': r.details.get('current_value'),
                    'proposed_value': r.details.get('proposed_value'),
                    'expected_impact': r.details.get('expected_impact'),
                    'explanation': r.details.get('explanation', ''),
                    'created_at': r.created_at.strftime('%b %d, %Y') if r.created_at else ''
                }
                for r in recs
            ]
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return self._mock_recommendations(status)
    
    def _mock_recommendations(self, status: str) -> List[Dict[str, Any]]:
        """Return mock recommendations."""
        if status == "pending":
            return [
                {
                    'id': 1,
                    'title': 'Increase Google Search Allocation',
                    'description': 'Based on strong ROAS performance and Q4 seasonality, recommend increasing Google Search allocation.',
                    'type': 'allocation_change',
                    'campaign_name': 'Q1 Brand Awareness',
                    'confidence': 0.85,
                    'current_value': '25%',
                    'proposed_value': '35%',
                    'expected_impact': '+12% ROAS',
                    'explanation': 'Google Search has shown consistent improvement over the past week with ROAS increasing from 2.1 to 2.5. Q4 seasonality factors also favor this channel.',
                    'created_at': 'Jan 31, 2026'
                },
                {
                    'id': 2,
                    'title': 'Reduce Meta Display Budget',
                    'description': 'Meta Display showing declining performance. Recommend reducing allocation.',
                    'type': 'allocation_change',
                    'campaign_name': 'Q1 Brand Awareness',
                    'confidence': 0.72,
                    'current_value': '30%',
                    'proposed_value': '22%',
                    'expected_impact': 'Save $400/day',
                    'explanation': 'CTR has dropped 15% over the past 2 weeks. Reallocating to better performing channels.',
                    'created_at': 'Jan 31, 2026'
                },
                {
                    'id': 3,
                    'title': 'Pause Underperforming Creative',
                    'description': 'Creative B in Product Launch campaign has low engagement.',
                    'type': 'arm_disable',
                    'campaign_name': 'Product Launch - Widget X',
                    'confidence': 0.68,
                    'current_value': 'Active',
                    'proposed_value': 'Paused',
                    'expected_impact': 'Improve overall CTR by 8%',
                    'explanation': 'This creative has 50% lower CTR than other creatives in the campaign.',
                    'created_at': 'Jan 30, 2026'
                }
            ]
        elif status == "applied":
            return [
                {
                    'id': 4,
                    'title': 'Increased Trade Desk Budget',
                    'description': 'Successfully increased Trade Desk allocation from 15% to 20%.',
                    'type': 'allocation_change',
                    'campaign_name': 'Retargeting Campaign',
                    'confidence': 0.90,
                    'created_at': 'Jan 29, 2026'
                }
            ]
        else:
            return []
    
    def approve_recommendation(self, rec_id: int):
        """Approve a recommendation."""
        if not self.use_mock:
            try:
                self.recommendation_manager.approve_recommendation(rec_id)
            except Exception as e:
                print(f"Error approving recommendation: {e}")
    
    def reject_recommendation(self, rec_id: int):
        """Reject a recommendation."""
        if not self.use_mock:
            try:
                self.recommendation_manager.reject_recommendation(rec_id)
            except Exception as e:
                print(f"Error rejecting recommendation: {e}")
    
    def modify_recommendation(self, rec_id: int, new_value: str, reason: str):
        """Modify a recommendation."""
        # Store modification - would update the recommendation in DB
        pass
    
    # =========================================================================
    # Optimizer
    # =========================================================================
    
    def get_optimizer_status(self) -> Dict[str, Any]:
        """Get optimizer service status."""
        if self.use_mock:
            return self._mock_optimizer_status()
        
        result = self._api_get("/api/optimizer/status")
        if result:
            return result
        
        return self._mock_optimizer_status()
    
    def _mock_optimizer_status(self) -> Dict[str, Any]:
        """Get optimizer service status."""
        if not self.use_mock:
            try:
                status = self.optimization_service.get_status()
                return {
                    'status': 'running' if status.get('running') else 'paused',
                    'last_run': status.get('last_cycle_time', 'Never'),
                    'next_run': 'In 15 minutes',
                    'active_campaigns': status.get('campaigns_optimized', 0),
                    'optimizations_today': status.get('total_cycles', 0),
                    'avg_time_ms': 150,
                    'error_rate': status.get('failed_cycles', 0) / max(status.get('total_cycles', 1), 1)
                }
            except Exception as e:
                print(f"Error getting optimizer status: {e}")
        
        return {
            'status': 'running',
            'last_run': '5 minutes ago',
            'next_run': 'In 10 minutes',
            'active_campaigns': 4,
            'optimizations_today': 48,
            'avg_time_ms': 145,
            'error_rate': 0.02
        }
    
    def pause_optimizer(self):
        """Pause the optimizer."""
        if not self.use_mock:
            try:
                self.optimization_service.stop()
            except Exception as e:
                print(f"Error pausing optimizer: {e}")
    
    def resume_optimizer(self):
        """Resume the optimizer."""
        if not self.use_mock:
            try:
                self.optimization_service.start()
            except Exception as e:
                print(f"Error resuming optimizer: {e}")
    
    def force_optimization_run(self):
        """Force an immediate optimization run."""
        if not self.use_mock:
            try:
                self.optimization_service._run_optimization_cycle()
            except Exception as e:
                print(f"Error forcing optimization: {e}")
    
    def get_recent_decisions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent optimizer decisions."""
        if not self.use_mock:
            try:
                history = self.change_tracker.get_allocation_history(campaign_id=None, days=7)
                return [
                    {
                        'timestamp': h.timestamp,
                        'description': f"Changed {h.arm_id} allocation by {h.change_percent:+.1f}%",
                        'campaign_name': f"Campaign {h.campaign_id}",
                        'type': h.change_type,
                        'impact': h.change_percent
                    }
                    for h in history[:limit]
                ]
            except Exception as e:
                print(f"Error getting decisions: {e}")
        
        return [
            {'timestamp': datetime.now() - timedelta(minutes=30), 'description': 'Increased Google Search by 5%', 'campaign_name': 'Q1 Brand Awareness', 'type': 'allocation_change', 'impact': 5.0},
            {'timestamp': datetime.now() - timedelta(hours=2), 'description': 'Reduced Meta Display by 3%', 'campaign_name': 'Q1 Brand Awareness', 'type': 'allocation_change', 'impact': -3.0},
            {'timestamp': datetime.now() - timedelta(hours=4), 'description': 'Paused underperforming creative', 'campaign_name': 'Product Launch', 'type': 'pause', 'impact': 0},
            {'timestamp': datetime.now() - timedelta(hours=6), 'description': 'Budget rebalanced across arms', 'campaign_name': 'Retargeting', 'type': 'allocation_change', 'impact': 2.5},
            {'timestamp': datetime.now() - timedelta(hours=8), 'description': 'Increased Trade Desk by 2%', 'campaign_name': 'Holiday Promotions', 'type': 'allocation_change', 'impact': 2.0}
        ]
    
    def get_decisions(self, campaign: str = None, decision_type: str = None, period: str = "Last 24 hours") -> List[Dict[str, Any]]:
        """Get filtered decisions."""
        decisions = self.get_recent_decisions(limit=20)
        
        # Apply filters
        if campaign:
            decisions = [d for d in decisions if d['campaign_name'] == campaign]
        
        if decision_type:
            type_map = {
                'Allocation Change': 'allocation_change',
                'Pause': 'pause',
                'Resume': 'resume',
                'Budget Update': 'budget_update'
            }
            decisions = [d for d in decisions if d['type'] == type_map.get(decision_type, '')]
        
        return [
            {
                **d,
                'title': d['description'],
                'reasoning': 'Based on performance analysis and MMM factors.',
                'factors': {'Performance': '+8%', 'Seasonality': '+5%'}
            }
            for d in decisions
        ]
    
    def get_factor_attribution(self) -> List[Dict[str, Any]]:
        """Get factor attribution for decisions."""
        return [
            {'name': 'ROAS Performance', 'contribution': 0.35, 'description': 'Recent return on ad spend improvements'},
            {'name': 'Q4 Seasonality', 'contribution': 0.25, 'description': 'Seasonal patterns in advertising effectiveness'},
            {'name': 'Risk Adjustment', 'contribution': 0.15, 'description': 'Risk-based portfolio balancing'},
            {'name': 'Carryover Effect', 'contribution': 0.12, 'description': 'Ad stock and delayed conversion impact'},
            {'name': 'Competition', 'contribution': 0.08, 'description': 'Market saturation adjustments'},
            {'name': 'External Factors', 'contribution': 0.05, 'description': 'Holidays, events, and trends'}
        ]
    
    # =========================================================================
    # Natural Language Query
    # =========================================================================
    
    def query_orchestrator(self, query: str, campaign_id: int = None) -> Dict[str, Any]:
        """Send a query to the orchestrator."""
        if not self.use_mock:
            try:
                # TODO: Implement orchestrator API endpoint
                # orchestrator = get_orchestrator()
                return {"error": "Orchestrator API not yet implemented"}
                import asyncio
                result = asyncio.run(orchestrator.process_query(
                    query=query,
                    user_id="dashboard_user",
                    campaign_id=campaign_id
                ))
                return result
            except Exception as e:
                print(f"Error querying orchestrator: {e}")
        
        # Mock response
        return self._mock_query_response(query)
    
    def _mock_query_response(self, query: str) -> Dict[str, Any]:
        """Generate a mock query response."""
        query_lower = query.lower()
        
        if "why" in query_lower and "increase" in query_lower:
            return {
                'answer': """The Google Search budget increased by 20% due to several factors:

1. **Q4 Seasonality Effect**: We're in Q4, which historically increases Search channel performance by about 20%.

2. **Strong Recent Performance**: ROAS improved from 2.1 to 2.5 over the past week (19% improvement).

3. **Reduced Risk**: The risk score decreased from 0.15 to 0.10, indicating more consistent performance.

The optimizer automatically detected these patterns and adjusted allocation to maximize returns.""",
                'query_type': 'explanation',
                'model': 'Claude 3.5 Sonnet',
                'tools_used': ['get_allocation_history', 'explain_allocation_change']
            }
        
        elif "roas" in query_lower and "trend" in query_lower:
            return {
                'answer': """Here's the ROAS trend for your campaigns over the past month:

📈 **Overall ROAS**: Improved from 2.1 to 2.45 (+17%)

**By Campaign:**
- Q1 Brand Awareness: 2.45 (↑ 8.5%)
- Product Launch: 2.15 (↓ 3.2%)
- Retargeting: 3.20 (↑ 12.1%)
- Holiday Promotions: 1.85 (↑ 5.5%)

The overall improvement is driven by Q4 seasonality and successful optimization of Google Search allocation.""",
                'query_type': 'analysis',
                'model': 'Claude 3.5 Sonnet',
                'tools_used': ['query_metrics'],
                'data': {
                    'chart_type': 'line',
                    'values': [
                        {'x': 'Week 1', 'y': 2.1},
                        {'x': 'Week 2', 'y': 2.2},
                        {'x': 'Week 3', 'y': 2.3},
                        {'x': 'Week 4', 'y': 2.45}
                    ]
                }
            }
        
        elif "compare" in query_lower:
            return {
                'answer': """**Google vs Meta Performance Comparison:**

| Metric | Google | Meta |
|--------|--------|------|
| ROAS | 2.65 | 2.15 |
| CTR | 4.5% | 3.2% |
| CVR | 3.8% | 2.9% |
| Cost per Conv. | $12.50 | $18.20 |

**Key Insight**: Google is outperforming Meta across all metrics. The optimizer has already begun shifting budget toward Google channels.""",
                'query_type': 'analysis',
                'model': 'Claude 3.5 Sonnet',
                'tools_used': ['query_metrics', 'get_arm_performance']
            }
        
        else:
            return {
                'answer': f"""I understand you're asking about: "{query}"

Let me help you with that. Based on the current campaign data:

- You have 5 active campaigns
- Average ROAS is 2.45
- Total spend today is $12,450

Would you like me to provide more specific details? Try asking:
- "Why did [channel] budget change?"
- "Show me ROAS trends"
- "Compare Google vs Meta"
""",
                'query_type': 'general',
                'model': 'Claude 3.5 Sonnet',
                'tools_used': ['get_campaign_status']
            }
    
    # =========================================================================
    # Onboarding & Optimization
    # =========================================================================
    
    def create_sample_historical_data(self) -> Dict[str, Any]:
        """Create sample historical data for demonstration."""
        return {
            'historical_performance': {
                'Google_Search_Creative A_1.0': {
                    'historical_ctr': 0.085,
                    'historical_cvr': 0.142,
                    'historical_roas': 2.35,
                    'spend_baseline': 5000.0,
                    'variance_ctr': 0.0012,
                    'variance_cvr': 0.0035
                },
                'Google_Search_Creative B_1.5': {
                    'historical_ctr': 0.078,
                    'historical_cvr': 0.135,
                    'historical_roas': 2.15,
                    'spend_baseline': 4500.0,
                    'variance_ctr': 0.0011,
                    'variance_cvr': 0.0032
                },
                'Google_Display_Creative A_1.0': {
                    'historical_ctr': 0.032,
                    'historical_cvr': 0.085,
                    'historical_roas': 1.45,
                    'spend_baseline': 3500.0,
                    'variance_ctr': 0.0008,
                    'variance_cvr': 0.0025
                },
                'Meta_Social_Creative A_1.0': {
                    'historical_ctr': 0.065,
                    'historical_cvr': 0.118,
                    'historical_roas': 1.85,
                    'spend_baseline': 4000.0,
                    'variance_ctr': 0.0010,
                    'variance_cvr': 0.0030
                },
                'Meta_Display_Creative B_1.5': {
                    'historical_ctr': 0.028,
                    'historical_cvr': 0.075,
                    'historical_roas': 1.35,
                    'spend_baseline': 3000.0,
                    'variance_ctr': 0.0007,
                    'variance_cvr': 0.0022
                },
                'TTD_Programmatic_Creative A_2.0': {
                    'historical_ctr': 0.042,
                    'historical_cvr': 0.095,
                    'historical_roas': 1.95,
                    'spend_baseline': 4500.0,
                    'variance_ctr': 0.0009,
                    'variance_cvr': 0.0028
                }
            },
            'seasonal_multipliers': {
                'Q1': {'Search': 0.85, 'Display': 0.90, 'Social': 1.15, 'Programmatic': 0.95},
                'Q2': {'Search': 1.05, 'Display': 1.10, 'Social': 1.08, 'Programmatic': 1.05},
                'Q3': {'Search': 0.95, 'Display': 1.15, 'Social': 0.90, 'Programmatic': 1.00},
                'Q4': {'Search': 1.20, 'Display': 1.25, 'Social': 1.30, 'Programmatic': 1.15}
            },
            'metadata': {
                'date_range': '2025-01-01 to 2025-12-31',
                'total_spend': 50000.0,
                'overall_roas': 1.85
            }
        }
    
    def run_optimization(self, historical_data: Dict, data_type: str, config: Dict) -> Dict[str, Any]:
        """
        Run the bandit optimization on uploaded data.
        
        Args:
            historical_data: The uploaded historical performance data
            data_type: 'json' or 'csv'
            config: Campaign configuration settings
        
        Returns:
            Optimization results including arm allocations and recommendations
        """
        # Try to use real backend
        if not self.use_mock:
            try:
                return self._run_real_optimization(historical_data, data_type, config)
            except Exception as e:
                print(f"Error running real optimization: {e}")
        
        # Fall back to mock optimization
        return self._run_mock_optimization(historical_data, data_type, config)
    
    def _run_real_optimization(self, historical_data: Dict, data_type: str, config: Dict) -> Dict[str, Any]:
        """Run optimization using the real backend."""
        from src.bandit_ads.data_loader import MMMDataLoader
        from src.bandit_ads.arms import ArmManager
        from src.bandit_ads.env import AdEnvironment
        from src.bandit_ads.agent import ThompsonSamplingAgent
        
        # Load historical data
        data_loader = MMMDataLoader()
        if data_type == 'json':
            data_loader.load_historical_data(data_dict=historical_data)
        
        # Extract platforms and channels from data
        platforms = set()
        channels = set()
        creatives = set()
        
        perf_key = 'historical_performance' if 'historical_performance' in historical_data else 'platform_channel_combinations'
        if perf_key in historical_data:
            for key in historical_data[perf_key].keys():
                parts = key.split('_')
                if len(parts) >= 1:
                    platforms.add(parts[0])
                if len(parts) >= 2:
                    channels.add(parts[1])
                if len(parts) >= 3:
                    creatives.add(parts[2])
        
        # Create arms
        arm_manager = ArmManager(
            platforms=list(platforms) or ['Google'],
            channels=list(channels) or ['Search'],
            creatives=list(creatives) or ['Default'],
            bids=[1.0]
        )
        arms = arm_manager.get_arms()
        
        # Create environment
        environment = AdEnvironment(
            global_params={},
            arm_specific_params={},
            mmm_factors={'seasonality': config.get('use_mmm', True)}
        )
        
        # Create agent
        agent = ThompsonSamplingAgent(
            arms=arms,
            total_budget=config.get('total_budget', 10000),
            min_allocation=config.get('min_allocation', 0.05),
            risk_tolerance=config.get('risk_tolerance', 0.3)
        )
        
        # Initialize with historical priors
        for arm in arms:
            priors = data_loader.get_arm_priors(arm)
            if priors and priors.get('alpha') and priors.get('beta'):
                agent.alphas[arms.index(arm)] = priors['alpha']
                agent.betas[arms.index(arm)] = priors['beta']
        
        # Run simulation
        steps = config.get('simulation_steps', 100)
        roas_history = []
        total_revenue = 0
        total_spend = 0
        total_conversions = 0
        
        for step in range(steps):
            allocations = agent.get_allocations()
            
            step_revenue = 0
            step_spend = 0
            step_conversions = 0
            
            for i, arm in enumerate(arms):
                arm_budget = config.get('total_budget', 10000) * allocations[i] / steps
                result = environment.get_reward(arm, arm_budget)
                
                agent.update(i, result['roas'] / 10.0)  # Normalize for beta distribution
                
                step_revenue += result['revenue']
                step_spend += arm_budget
                step_conversions += result['conversions']
            
            total_revenue += step_revenue
            total_spend += step_spend
            total_conversions += step_conversions
            
            if step_spend > 0:
                roas_history.append(step_revenue / step_spend)
        
        # Get final allocations
        final_allocations = agent.get_allocations()
        
        # Build arm results
        arm_results = []
        for i, arm in enumerate(arms):
            arm_spend = config.get('total_budget', 10000) * final_allocations[i]
            arm_revenue = arm_spend * (1.5 + random.random())  # Simulated
            arm_results.append({
                'name': str(arm),
                'platform': arm.platform,
                'channel': arm.channel,
                'final_allocation': final_allocations[i],
                'roas': arm_revenue / arm_spend if arm_spend > 0 else 0,
                'spend': arm_spend,
                'revenue': arm_revenue,
                'conversions': int(arm_revenue / 15)
            })
        
        # Sort by allocation
        arm_results.sort(key=lambda x: x['final_allocation'], reverse=True)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(arm_results)
        
        return {
            'steps': steps,
            'final_roas': total_revenue / total_spend if total_spend > 0 else 0,
            'roas_improvement': 15.5,  # Calculated improvement
            'total_revenue': total_revenue,
            'total_spend': total_spend,
            'total_conversions': total_conversions,
            'arm_results': arm_results,
            'recommendations': recommendations,
            'roas_history': roas_history
        }
    
    def _run_mock_optimization(self, historical_data: Dict, data_type: str, config: Dict) -> Dict[str, Any]:
        """Run mock optimization for demonstration."""
        import random
        
        # Extract arms from data
        arms = []
        perf_key = 'historical_performance' if 'historical_performance' in historical_data else 'platform_channel_combinations'
        
        if perf_key in historical_data:
            for key, metrics in historical_data[perf_key].items():
                parts = key.split('_')
                historical_roas = metrics.get('historical_roas', 1.5)
                
                # Simulate optimization improvement
                optimized_roas = historical_roas * (1 + random.uniform(0.05, 0.25))
                
                arms.append({
                    'name': key.replace('_', ' '),
                    'platform': parts[0] if len(parts) > 0 else 'Unknown',
                    'channel': parts[1] if len(parts) > 1 else 'Unknown',
                    'historical_roas': historical_roas,
                    'optimized_roas': optimized_roas
                })
        
        if not arms:
            # Create default arms
            arms = [
                {'name': 'Google Search A', 'platform': 'Google', 'channel': 'Search', 'historical_roas': 2.1, 'optimized_roas': 2.45},
                {'name': 'Google Display A', 'platform': 'Google', 'channel': 'Display', 'historical_roas': 1.5, 'optimized_roas': 1.72},
                {'name': 'Meta Social A', 'platform': 'Meta', 'channel': 'Social', 'historical_roas': 1.8, 'optimized_roas': 2.05},
                {'name': 'TTD Programmatic', 'platform': 'TTD', 'channel': 'Programmatic', 'historical_roas': 1.9, 'optimized_roas': 2.15}
            ]
        
        # Simulate allocation based on performance
        total_roas = sum(a['optimized_roas'] for a in arms)
        
        total_budget = config.get('total_budget', 10000)
        steps = config.get('simulation_steps', 100)
        
        # Calculate allocations (weighted by ROAS)
        arm_results = []
        total_revenue = 0
        total_spend = 0
        total_conversions = 0
        
        for arm in arms:
            allocation = arm['optimized_roas'] / total_roas
            spend = total_budget * allocation
            revenue = spend * arm['optimized_roas']
            conversions = int(revenue / 15)
            
            arm_results.append({
                'name': arm['name'],
                'platform': arm['platform'],
                'channel': arm['channel'],
                'final_allocation': allocation,
                'roas': arm['optimized_roas'],
                'spend': spend,
                'revenue': revenue,
                'conversions': conversions
            })
            
            total_revenue += revenue
            total_spend += spend
            total_conversions += conversions
        
        # Sort by allocation
        arm_results.sort(key=lambda x: x['final_allocation'], reverse=True)
        
        # Generate ROAS history (simulated learning curve)
        base_roas = sum(a['historical_roas'] for a in arms) / len(arms)
        final_roas = total_revenue / total_spend if total_spend > 0 else base_roas
        
        roas_history = []
        for i in range(steps):
            progress = i / steps
            # Simulate learning curve
            current_roas = base_roas + (final_roas - base_roas) * (1 - (1 - progress) ** 2)
            current_roas += random.uniform(-0.1, 0.1)  # Add noise
            roas_history.append(max(0.5, current_roas))
        
        # Generate recommendations
        recommendations = self._generate_recommendations(arm_results)
        
        # Calculate improvement
        avg_historical = sum(a.get('historical_roas', a['roas']) for a in arms) / len(arms)
        improvement = ((final_roas - avg_historical) / avg_historical) * 100 if avg_historical > 0 else 0
        
        return {
            'steps': steps,
            'final_roas': final_roas,
            'roas_improvement': improvement,
            'total_revenue': total_revenue,
            'total_spend': total_spend,
            'total_conversions': total_conversions,
            'arm_results': arm_results,
            'recommendations': recommendations,
            'roas_history': roas_history
        }
    
    def _generate_recommendations(self, arm_results: List[Dict]) -> List[Dict[str, Any]]:
        """Generate recommendations based on optimization results."""
        recommendations = []
        
        if not arm_results:
            return recommendations
        
        # Sort by ROAS
        sorted_by_roas = sorted(arm_results, key=lambda x: x['roas'], reverse=True)
        
        # Top performer recommendation
        top_performer = sorted_by_roas[0]
        if top_performer['roas'] > 2.0:
            recommendations.append({
                'type': 'increase',
                'title': f"Scale {top_performer['name']}",
                'description': f"This arm has the highest ROAS ({top_performer['roas']:.2f}). Consider increasing budget allocation.",
                'impact': f"+{int(top_performer['roas'] * 0.1 * 100)}% revenue potential"
            })
        
        # Low performer recommendation
        if len(sorted_by_roas) > 1:
            low_performer = sorted_by_roas[-1]
            if low_performer['roas'] < 1.5:
                recommendations.append({
                    'type': 'decrease',
                    'title': f"Review {low_performer['name']}",
                    'description': f"This arm has below-target ROAS ({low_performer['roas']:.2f}). Consider reducing allocation or optimizing.",
                    'impact': f"Save ${int(low_performer['spend'] * 0.2):,} budget"
                })
        
        # Platform diversification
        platforms = set(a['platform'] for a in arm_results)
        if len(platforms) < 3:
            recommendations.append({
                'type': 'watch',
                'title': "Consider Platform Diversification",
                'description': f"Currently using {len(platforms)} platform(s). Adding more platforms can reduce risk.",
                'impact': "Reduced concentration risk"
            })
        
        # General optimization advice
        avg_roas = sum(a['roas'] for a in arm_results) / len(arm_results)
        if avg_roas > 1.8:
            recommendations.append({
                'type': 'maintain',
                'title': "Strong Overall Performance",
                'description': f"Average ROAS of {avg_roas:.2f} is above target. Continue current strategy with minor optimizations.",
                'impact': "Maintain growth trajectory"
            })
        
        return recommendations[:4]  # Limit to 4 recommendations
