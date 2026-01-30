"""
Contextual Bandit Agent for ad spend optimization.

Extends the basic bandit to incorporate contextual features (user demographics,
time-of-day, device, etc.) for more granular optimization.
"""

import random
import math
from collections import defaultdict
from typing import Dict, List, Any, Optional
from src.bandit_ads.agent import ThompsonSamplingAgent
from src.bandit_ads.context_features import ContextFeatureExtractor
from src.bandit_ads.arms import Arm


class ContextualBanditAgent(ThompsonSamplingAgent):
    """
    Contextual bandit agent that learns arm performance conditioned on context.
    
    Uses a linear model to learn context-arm interactions:
    - Each arm has a linear model: reward = context^T * theta_arm
    - Uses LinUCB-style approach for exploration/exploitation
    - Falls back to standard Thompson Sampling when context is not provided
    """
    
    def __init__(self, arms, total_budget, min_allocation=0.01, 
                 risk_tolerance=0.3, variance_limit=0.1,
                 context_config: Optional[Dict[str, Any]] = None,
                 alpha: float = 1.0):
        """
        Initialize contextual bandit agent.
        
        Args:
            arms: List of Arm objects
            total_budget: Total budget to allocate
            min_allocation: Minimum budget fraction per arm
            risk_tolerance: Risk tolerance (0.0 = risk-averse, 1.0 = risk-neutral)
            variance_limit: Maximum allowed variance
            context_config: Configuration for context features (see ContextFeatureExtractor)
            alpha: Exploration parameter for LinUCB (higher = more exploration)
        """
        super().__init__(arms, total_budget, min_allocation, risk_tolerance, variance_limit)
        
        # Context feature extractor
        self.context_extractor = ContextFeatureExtractor(context_config)
        self.feature_dim = self.context_extractor.get_feature_dimension()
        self.ucb_alpha = alpha  # LinUCB exploration parameter (renamed to avoid conflict with parent's alpha dict)
        
        # Linear model parameters for each arm: theta_arm (feature_dim x 1)
        # Using ridge regression: A_arm * theta_arm = b_arm
        self.arm_A = {}  # A_arm: feature_dim x feature_dim matrix (as dict of dicts)
        self.arm_b = {}  # b_arm: feature_dim x 1 vector
        self.arm_theta = {}  # Cached theta estimates
        
        # Initialize linear models for each arm
        for arm in arms:
            arm_key = str(arm)
            # Initialize A as identity matrix (ridge regularization)
            self.arm_A[arm_key] = defaultdict(lambda: defaultdict(float))
            for i in range(self.feature_dim):
                self.arm_A[arm_key][i][i] = 1.0  # Identity matrix
            self.arm_b[arm_key] = [0.0] * self.feature_dim
            self.arm_theta[arm_key] = [0.0] * self.feature_dim
        
        # Track context-specific performance
        self.context_arm_rewards = defaultdict(lambda: defaultdict(float))
        self.context_arm_trials = defaultdict(lambda: defaultdict(int))
    
    def _update_linear_model(self, arm_key: str, context: List[float], reward: float):
        """
        Update linear model for an arm using ridge regression.
        
        Uses incremental update: A += context * context^T, b += context * reward
        """
        # Update A matrix: A += context * context^T
        for i in range(self.feature_dim):
            for j in range(self.feature_dim):
                self.arm_A[arm_key][i][j] += context[i] * context[j]
        
        # Update b vector: b += context * reward
        for i in range(self.feature_dim):
            self.arm_b[arm_key][i] += context[i] * reward
        
        # Recompute theta: theta = A^(-1) * b
        # Using simple matrix inversion (for small feature dimensions)
        self.arm_theta[arm_key] = self._solve_linear_system(
            self.arm_A[arm_key], self.arm_b[arm_key]
        )
    
    def _solve_linear_system(self, A: Dict[int, Dict[int, float]], 
                              b: List[float]) -> List[float]:
        """
        Solve A * x = b using Gaussian elimination (simplified for small systems).
        
        For larger systems, consider using numpy or scipy.
        """
        n = len(b)
        
        # Convert A to list of lists
        A_matrix = [[A[i].get(j, 0.0) for j in range(n)] for i in range(n)]
        
        # Gaussian elimination with partial pivoting
        for i in range(n):
            # Find pivot
            max_row = i
            for k in range(i + 1, n):
                if abs(A_matrix[k][i]) > abs(A_matrix[max_row][i]):
                    max_row = k
            
            # Swap rows
            A_matrix[i], A_matrix[max_row] = A_matrix[max_row], A_matrix[i]
            b[i], b[max_row] = b[max_row], b[i]
            
            # Eliminate
            for k in range(i + 1, n):
                if abs(A_matrix[i][i]) < 1e-10:
                    continue
                factor = A_matrix[k][i] / A_matrix[i][i]
                for j in range(i, n):
                    A_matrix[k][j] -= factor * A_matrix[i][j]
                b[k] -= factor * b[i]
        
        # Back substitution
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            x[i] = b[i]
            for j in range(i + 1, n):
                x[i] -= A_matrix[i][j] * x[j]
            if abs(A_matrix[i][i]) > 1e-10:
                x[i] /= A_matrix[i][i]
        
        return x
    
    def _compute_ucb_score(self, arm_key: str, context: List[float]) -> float:
        """
        Compute Upper Confidence Bound score for an arm given context.
        
        UCB = context^T * theta_arm + alpha * sqrt(context^T * A^(-1) * context)
        """
        # Expected reward: context^T * theta
        expected_reward = sum(context[i] * self.arm_theta[arm_key][i] 
                             for i in range(self.feature_dim))
        
        # Confidence interval: sqrt(context^T * A^(-1) * context)
        # Approximate using diagonal elements for efficiency
        confidence = 0.0
        A_inv_diag = [1.0 / max(self.arm_A[arm_key][i][i], 1e-6) 
                     for i in range(self.feature_dim)]
        confidence = math.sqrt(sum(context[i] ** 2 * A_inv_diag[i] 
                                   for i in range(self.feature_dim)))
        
        ucb_score = expected_reward + self.ucb_alpha * confidence
        
        return ucb_score
    
    def select_arm(self, context: Optional[Dict[str, Any]] = None):
        """
        Select the best arm given context.
        
        Args:
            context: Optional context dictionary (user_data, timestamp)
                    If None, falls back to standard Thompson Sampling
        
        Returns:
            Selected Arm
        """
        # If no context provided, use parent's standard selection
        if context is None:
            return super().select_arm()
        
        # Extract and encode context
        context_dict = self.context_extractor.extract_context(
            user_data=context.get('user_data'),
            timestamp=context.get('timestamp')
        )
        context_vector = self.context_extractor.encode_context_vector(context_dict)
        
        # Compute UCB scores for all arms
        ucb_scores = {}
        for arm in self.arms:
            arm_key = str(arm)
            ucb_scores[arm_key] = self._compute_ucb_score(arm_key, context_vector)
        
        # Select arm with highest UCB score (if budget allows)
        # Consider budget allocation
        remaining_budget = self.total_budget - self.total_spent
        if remaining_budget <= 0:
            return None
        
        # Filter arms by remaining budget
        eligible_arms = []
        for arm in self.arms:
            arm_key = str(arm)
            remaining = self.current_allocation.get(arm_key, 0) - self.arm_spending[arm_key]
            if remaining > 0:
                eligible_arms.append((arm, ucb_scores[arm_key]))
        
        if not eligible_arms:
            # Reallocate budget if needed
            self.current_allocation = self._allocate_budget()
            eligible_arms = [(arm, ucb_scores[str(arm)]) 
                           for arm in self.arms 
                           if self.current_allocation.get(str(arm), 0) > 0]
        
        if eligible_arms:
            # Select arm with highest UCB score
            selected_arm, _ = max(eligible_arms, key=lambda x: x[1])
            return selected_arm
        
        return random.choice(self.arms)
    
    def update(self, arm, result, cost_per_impression=0.01, 
               context: Optional[Dict[str, Any]] = None):
        """
        Update the agent with feedback, incorporating context if provided.
        
        Args:
            arm: Arm that was pulled
            result: Dictionary with metrics from environment
            cost_per_impression: Cost per impression
            context: Optional context dictionary
        """
        arm_key = str(arm)
        
        # Update parent's standard tracking
        super().update(arm, result, cost_per_impression)
        
        # If context provided, update linear model
        if context is not None:
            context_dict = self.context_extractor.extract_context(
                user_data=context.get('user_data'),
                timestamp=context.get('timestamp')
            )
            context_vector = self.context_extractor.encode_context_vector(context_dict)
            
            # Use ROAS as reward signal
            reward = result.get('roas', 0.0)
            
            # Update linear model
            self._update_linear_model(arm_key, context_vector, reward)
            
            # Track context-specific performance
            context_key = self._context_to_key(context_dict)
            self.context_arm_rewards[context_key][arm_key] += reward
            self.context_arm_trials[context_key][arm_key] += 1
    
    def _context_to_key(self, context: Dict[str, Any]) -> str:
        """Convert context to a hash key for tracking."""
        # Use a subset of active features for key
        active_features = []
        for name in self.context_extractor.get_feature_names():
            if context.get(name, 0.0) > 0.5:  # Binary features
                active_features.append(name)
        return '_'.join(sorted(active_features))
    
    def get_contextual_performance(self) -> Dict[str, Any]:
        """
        Get performance metrics broken down by context.
        
        Returns:
            Dictionary with context-specific performance
        """
        context_perf = {}
        for context_key, arm_rewards in self.context_arm_rewards.items():
            context_perf[context_key] = {}
            for arm_key, total_reward in arm_rewards.items():
                trials = self.context_arm_trials[context_key][arm_key]
                context_perf[context_key][arm_key] = {
                    'avg_reward': total_reward / trials if trials > 0 else 0.0,
                    'trials': trials
                }
        return context_perf
    
    def get_performance_metrics(self):
        """Get performance metrics including contextual information."""
        metrics = super().get_performance_metrics()
        metrics['contextual_performance'] = self.get_contextual_performance()
        metrics['feature_dimension'] = self.feature_dim
        return metrics
