import random
import math
from collections import defaultdict

class ThompsonSamplingAgent:
    """
    Multi-armed bandit agent using Thompson Sampling for ad spend optimization.

    Includes risk constraints to balance expected returns with variance limits.
    Optimizes for total ROAS while controlling downside risk.
    """

    def __init__(self, arms, total_budget, min_allocation=0.01, risk_tolerance=0.3, variance_limit=0.1):
        """
        Initialize the Thompson Sampling agent with risk constraints.

        Args:
            arms: List of Arm objects representing ad configurations
            total_budget: Total budget to allocate across arms
            min_allocation: Minimum budget fraction per arm (to ensure exploration)
            risk_tolerance: How much variance we're willing to accept (0.0 = risk-averse, 1.0 = risk-neutral)
            variance_limit: Maximum allowed variance in arm performance
        """
        self.arms = arms
        self.total_budget = total_budget
        self.min_allocation = min_allocation
        self.risk_tolerance = risk_tolerance
        self.variance_limit = variance_limit

        # Beta distribution parameters for each arm (alpha=successes+1, beta=failures+1)
        self.alpha = defaultdict(lambda: 1.0)  # successes (good ROAS outcomes)
        self.beta = defaultdict(lambda: 1.0)   # failures (poor ROAS outcomes)

        # Track spending and performance per arm
        self.arm_spending = defaultdict(float)
        self.arm_impressions = defaultdict(int)
        self.arm_rewards = defaultdict(float)  # cumulative ROAS-weighted rewards
        self.arm_reward_variance = defaultdict(float)  # track variance in rewards
        self.arm_trials = defaultdict(int)  # number of trials per arm

        # Risk-adjusted tracking
        self.arm_risk_scores = defaultdict(float)  # risk-adjusted performance scores

        # Track overall performance
        self.total_spent = 0.0
        self.total_reward = 0.0
        self.last_reallocation_fraction = 0.0  # Track last reallocation point

        # Budget allocation for current round
        self.current_allocation = self._allocate_budget()

    def _allocate_budget(self):
        """
        Allocate budget across arms using risk-constrained Thompson Sampling.

        Uses Upper Confidence Bound (UCB) with variance limits to balance
        exploration, exploitation, and risk control.

        Returns:
            dict: Mapping of arm to budget allocation
        """
        # Calculate risk-adjusted scores for each arm
        risk_adjusted_scores = {}
        variances = {}

        for arm in self.arms:
            arm_key = str(arm)
            trials = self.arm_trials[arm_key]

            if trials > 0:
                # Calculate variance of ROAS for this arm
                mean_roas = self.arm_rewards[arm_key] / self.arm_spending[arm_key] if self.arm_spending[arm_key] > 0 else 0
                variance = self.arm_reward_variance[arm_key]

                # Risk-adjusted score: expected return minus risk penalty
                risk_penalty = self.risk_tolerance * variance
                risk_adjusted_scores[arm_key] = mean_roas - risk_penalty
                variances[arm_key] = variance
            else:
                # For unexplored arms, use Thompson sampling
                risk_adjusted_scores[arm_key] = self._sample_beta(self.alpha[arm_key], self.beta[arm_key])
                variances[arm_key] = self.variance_limit  # Assume high variance for unexplored

        # Filter out arms that exceed variance limits (too risky)
        eligible_arms = {
            arm_key: score for arm_key, score in risk_adjusted_scores.items()
            if variances[arm_key] <= self.variance_limit
        }

        # If no arms meet variance criteria, relax constraints slightly
        if not eligible_arms:
            max_variance = max(variances.values()) if variances else self.variance_limit
            relaxed_limit = max_variance * 1.2
            eligible_arms = {
                arm_key: score for arm_key, score in risk_adjusted_scores.items()
                if variances[arm_key] <= relaxed_limit
            }

        # Allocate budget proportionally to risk-adjusted scores
        total_score = sum(eligible_arms.values())
        remaining_budget = self.total_budget - self.total_spent

        if remaining_budget <= 0:
            return {str(arm): 0.0 for arm in self.arms}

        allocation = {}
        min_budget = remaining_budget * self.min_allocation

        # Allocate to eligible arms
        for arm in self.arms:
            arm_key = str(arm)
            if arm_key in eligible_arms:
                # Proportional allocation based on risk-adjusted score
                proportion = eligible_arms[arm_key] / total_score if total_score > 0 else 1.0 / len(eligible_arms)
                allocated = max(min_budget, remaining_budget * proportion)
            else:
                # Minimum allocation for risky arms to encourage exploration
                allocated = min_budget * 0.5  # Half minimum for risky arms

            # Ensure we don't exceed remaining budget
            current_total = sum(allocation.values())
            if current_total + allocated > remaining_budget:
                allocated = max(0, remaining_budget - current_total)

            allocation[arm_key] = allocated

        return allocation

    def _sample_beta(self, alpha, beta, max_attempts=1000):
        """
        Sample from beta distribution using rejection sampling.
        For simplicity, falls back to uniform random if sampling fails.
        """
        # Simple approximation: use the mean with some noise
        # This is not perfect but works for demonstration
        mean = alpha / (alpha + beta)
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))

        # Add noise based on variance
        noise = random.gauss(0, math.sqrt(variance))
        sample = mean + noise

        # Clamp to [0, 1]
        return max(0.0, min(1.0, sample))

    def select_arm(self):
        """
        Select the best arm based on current budget allocation.

        Returns:
            Arm: Selected arm for next ad spend
        """
        # Find arm with highest remaining budget
        max_budget = 0
        selected_arm = None

        for arm in self.arms:
            arm_key = str(arm)
            remaining = self.current_allocation.get(arm_key, 0) - self.arm_spending[arm_key]
            if remaining > max_budget:
                max_budget = remaining
                selected_arm = arm

        return selected_arm if selected_arm else random.choice(self.arms)

    def update(self, arm, result, cost_per_impression=0.01):
        """
        Update the agent with feedback from pulling an arm.

        Args:
            arm: Arm that was pulled
            result: Dictionary with metrics from environment step
            cost_per_impression: Cost per ad impression (for budget tracking)
        """
        arm_key = str(arm)

        # Update spending and impressions
        impressions = result['impressions']
        cost = result['cost']
        roas = result['roas']

        self.arm_spending[arm_key] += cost
        self.arm_impressions[arm_key] += impressions
        self.total_spent += cost

        # Update beta distribution based on ROAS performance
        # Consider ROAS > 1.0 as "success", ROAS <= 1.0 as "failure"
        # Weight by the magnitude of ROAS difference from 1.0
        roas_performance = max(0, roas - 1.0)  # Only count positive ROAS above baseline

        if roas > 1.0:
            # Success: increment alpha (weighted by ROAS magnitude)
            weight = min(roas_performance, 10.0)  # Cap extreme values
            self.alpha[arm_key] += weight
        else:
            # Failure: increment beta
            self.beta[arm_key] += 1.0

        # Track cumulative reward (ROAS-weighted)
        self.arm_rewards[arm_key] += roas * cost  # Weight by spend amount
        self.total_reward += roas * cost

        # Update variance tracking for risk assessment
        self.arm_trials[arm_key] += 1
        trials = self.arm_trials[arm_key]

        if trials > 1:
            # Update running variance using Welford's online algorithm
            mean_roas = self.arm_rewards[arm_key] / self.arm_spending[arm_key] if self.arm_spending[arm_key] > 0 else 0
            prev_mean = (self.arm_rewards[arm_key] - roas * cost) / (self.arm_spending[arm_key] - cost) if (self.arm_spending[arm_key] - cost) > 0 else 0

            # Update variance incrementally
            delta = roas - prev_mean
            self.arm_reward_variance[arm_key] = ((trials - 2) * self.arm_reward_variance[arm_key] + delta * (roas - mean_roas)) / (trials - 1)
        else:
            # First trial
            self.arm_reward_variance[arm_key] = 0.0

        # Calculate risk score (combination of variance and downside risk)
        mean_roas = self.arm_rewards[arm_key] / self.arm_spending[arm_key] if self.arm_spending[arm_key] > 0 else 0
        variance_penalty = self.risk_tolerance * self.arm_reward_variance[arm_key]

        # Downside risk: penalize more for ROAS below 1.0
        downside_risk = max(0, 1.0 - mean_roas) if mean_roas < 1.0 else 0
        self.arm_risk_scores[arm_key] = mean_roas - variance_penalty - downside_risk

        # Re-allocate budget if we've crossed a 10% spending threshold since last reallocation
        spent_fraction = self.total_spent / self.total_budget
        current_threshold = int(spent_fraction * 10) / 10.0  # Round down to nearest 0.1
        last_threshold = int(self.last_reallocation_fraction * 10) / 10.0

        if current_threshold > last_threshold and current_threshold >= 0.1:
            self.current_allocation = self._allocate_budget()
            self.last_reallocation_fraction = spent_fraction

    def get_performance_metrics(self):
        """
        Get current performance metrics.

        Returns:
            dict: Performance metrics
        """
        return {
            'total_spent': self.total_spent,
            'total_budget': self.total_budget,
            'budget_utilization': self.total_spent / self.total_budget,
            'total_roas': self.total_reward / self.total_spent if self.total_spent > 0 else 0,
            'arm_performance': {
                str(arm): {
                    'spending': self.arm_spending[str(arm)],
                    'impressions': self.arm_impressions[str(arm)],
                    'avg_roas': self.arm_rewards[str(arm)] / self.arm_spending[str(arm)] if self.arm_spending[str(arm)] > 0 else 0,
                    'allocation': self.current_allocation.get(str(arm), 0),
                    'alpha': self.alpha[str(arm)],
                    'beta': self.beta[str(arm)]
                }
                for arm in self.arms
            }
        }

    def is_budget_exhausted(self):
        """Check if budget is exhausted."""
        return self.total_spent >= self.total_budget