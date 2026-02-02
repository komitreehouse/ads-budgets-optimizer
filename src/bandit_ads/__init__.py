"""
Bandit Ads - Budget Optimization System

This package provides:
- Multi-armed bandit optimization (Thompson Sampling)
- Contextual bandit optimization (LinUCB)
- Marketing Mix Modeling (MMM) integration
- Real-time API connectors for ad platforms
- Human interpretability layer with LLM-powered explanations
- MCP server for structured tool access

For simpler imports without full initialization, import directly from submodules:
    from src.bandit_ads.agent import ThompsonSamplingAgent
    from src.bandit_ads.explanation_generator import get_explanation_generator
"""

# Only import utilities that have no side effects
from src.bandit_ads.utils import get_logger, ConfigManager

__all__ = [
    "get_logger",
    "ConfigManager",
]

# For convenience, define lazy imports for common classes
def get_agent():
    """Get Thompson Sampling Agent class."""
    from src.bandit_ads.agent import ThompsonSamplingAgent
    return ThompsonSamplingAgent

def get_contextual_agent():
    """Get Contextual Bandit Agent class."""
    from src.bandit_ads.contextual_agent import ContextualBanditAgent
    return ContextualBanditAgent

def get_environment():
    """Get Ad Environment class."""
    from src.bandit_ads.env import AdEnvironment
    return AdEnvironment

def get_runner():
    """Get Ad Optimization Runner class."""
    from src.bandit_ads.runner import AdOptimizationRunner
    return AdOptimizationRunner
