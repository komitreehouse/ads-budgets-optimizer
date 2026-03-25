import random
import math
from collections import defaultdict

class ThompsonSamplingAgent:
    """
    Multi-armed bandit agent using Thompson Sampling for ad spend optimization.

    Includes risk constraints to balance expected returns with variance limits.
    Optimizes for total ROAS while controlling downside risk.
    
    Architecture Notes
    ------------------
    Current implementation uses Beta distributions for Thompson Sampling, which provides
    a lightweight Bayesian approach suitable for real-time optimization.

    Bayesian MMM integration is implemented via the Meridian pipeline; see
    meridian_bridge.py for posterior-to-Beta prior conversion.
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
        # Informative priors can be set from Meridian posteriors; see meridian_bridge.py
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


class IncrementalityAwareBandit(ThompsonSamplingAgent):
    """
    Thompson Sampling agent that incorporates incrementality experiment results
    into bandit priors.
    
    This is the key differentiator: incrementality results automatically feed back
    into the optimization, reallocating budget based on TRUE incremental ROAS
    rather than just observed (attributed) ROAS.
    
    The closed-loop system:
    1. Run holdout experiment to measure true incrementality
    2. Compare observed ROAS to incremental ROAS
    3. Adjust alpha/beta priors based on the gap
    4. Reallocate budget to arms with higher incremental value
    
    Bayesian integration: Meridian posteriors feed into incorporate_meridian_posteriors()
    to set calibrated alpha/beta priors. See meridian_bridge.py for the conversion logic.
    """
    
    def __init__(self, arms, total_budget, holdout_percentage=0.10, **kwargs):
        """
        Initialize incrementality-aware bandit.
        
        Args:
            arms: List of Arm objects representing ad configurations
            total_budget: Total budget to allocate across arms
            holdout_percentage: Percentage of budget/users to holdout (default 10%)
            **kwargs: Additional arguments passed to ThompsonSamplingAgent
        """
        # Initialize incrementality tracking before super().__init__ because
        # _allocate_budget() (called during init) references these
        self.incrementality_priors = {}  # arm_key -> incremental ROAS
        self.observed_vs_incremental = {}  # arm_key -> ratio of observed/incremental
        self.holdout_percentage = holdout_percentage

        super().__init__(arms, total_budget, **kwargs)
        
        # Holdout arm for tracking organic conversions
        from src.bandit_ads.incrementality import HoldoutArm
        self.holdout_arm = HoldoutArm(holdout_percentage=holdout_percentage)
        
        # Track whether incrementality adjustments have been applied
        self.incrementality_adjustments_applied = defaultdict(bool)
        
        # Adjustment history for explainability
        self.adjustment_history = []
    
    def record_holdout_metrics(
        self, 
        users: int, 
        conversions: int, 
        revenue: float,
        date=None
    ):
        """
        Record organic conversions from the holdout group.
        
        Call this with metrics from users who were NOT shown ads.
        
        Args:
            users: Number of users in holdout
            conversions: Conversions from holdout users
            revenue: Revenue from holdout users
            date: Date of metrics (optional)
        """
        self.holdout_arm.record_organic(users, conversions, revenue, date)
    
    def incorporate_incrementality(self, arm_key: str, experiment_result: dict):
        """
        Update arm priors based on incrementality experiment results.
        
        This is the KEY METHOD that closes the loop:
        - If incremental ROAS < observed ROAS: we were overestimating this arm
        - If incremental ROAS > observed ROAS: we were underestimating this arm
        
        Args:
            arm_key: String key for the arm
            experiment_result: Dictionary containing:
                - lift_percent: Incremental lift percentage
                - incremental_roas: True incremental ROAS
                - observed_roas: Attributed/observed ROAS
                - is_significant: Whether results are statistically significant
                - confidence_interval: (lower, upper) CI bounds
        
        Bayesian integration: see meridian_bridge.py for posterior → Beta prior conversion,
        and incorporate_meridian_posteriors() for the update flow.
        """
        if not experiment_result.get('is_significant', False):
            # Don't update priors if results aren't significant
            return
        
        incremental_roas = experiment_result.get('incremental_roas', 0)
        observed_roas = experiment_result.get('observed_roas', 0)
        
        if incremental_roas <= 0:
            # No incremental value - significant negative adjustment
            incremental_roas = 0.1  # Floor to avoid division issues
        
        # Store incrementality prior
        self.incrementality_priors[arm_key] = incremental_roas
        
        # Calculate ratio for tracking
        if observed_roas > 0:
            self.observed_vs_incremental[arm_key] = observed_roas / incremental_roas
        else:
            self.observed_vs_incremental[arm_key] = 1.0
        
        # Adjust beta distribution based on incrementality
        trials = self.arm_trials[arm_key]
        
        if trials > 0:
            # Calculate adjustment magnitude
            if observed_roas > 0:
                adjustment_ratio = incremental_roas / observed_roas
            else:
                adjustment_ratio = 1.0
            
            if incremental_roas < observed_roas:
                # We were OVERESTIMATING this arm
                # Increase beta (failures) to reduce its perceived value
                overestimate_factor = (observed_roas - incremental_roas) / observed_roas
                beta_adjustment = overestimate_factor * trials * 0.5  # 50% of trials as adjustment weight
                
                self.beta[arm_key] += beta_adjustment
                
                adjustment_record = {
                    'arm_key': arm_key,
                    'direction': 'decrease',
                    'reason': 'observed_roas_overestimated',
                    'observed_roas': observed_roas,
                    'incremental_roas': incremental_roas,
                    'beta_adjustment': beta_adjustment,
                    'timestamp': self._get_timestamp()
                }
            else:
                # We were UNDERESTIMATING this arm
                # Increase alpha (successes) to increase its perceived value
                underestimate_factor = (incremental_roas - observed_roas) / incremental_roas if incremental_roas > 0 else 0
                alpha_adjustment = underestimate_factor * trials * 0.5
                
                self.alpha[arm_key] += alpha_adjustment
                
                adjustment_record = {
                    'arm_key': arm_key,
                    'direction': 'increase',
                    'reason': 'observed_roas_underestimated',
                    'observed_roas': observed_roas,
                    'incremental_roas': incremental_roas,
                    'alpha_adjustment': alpha_adjustment,
                    'timestamp': self._get_timestamp()
                }
            
            self.adjustment_history.append(adjustment_record)
            self.incrementality_adjustments_applied[arm_key] = True
            
            # Force reallocation after adjustment
            self.current_allocation = self._allocate_budget()
    
    def _allocate_budget(self):
        """
        Override allocation to use incremental ROAS when available.
        
        This ensures budget flows to arms with highest TRUE incremental value,
        not just highest observed/attributed value.
        """
        # Start with parent allocation logic
        allocation = super()._allocate_budget()
        
        # If we have incrementality priors, adjust allocation
        if self.incrementality_priors:
            # Recalculate scores using incremental ROAS
            incremental_scores = {}
            
            for arm in self.arms:
                arm_key = str(arm)
                
                if arm_key in self.incrementality_priors:
                    # Use incremental ROAS as the score
                    incremental_scores[arm_key] = self.incrementality_priors[arm_key]
                else:
                    # Fall back to observed performance
                    if self.arm_spending[arm_key] > 0:
                        incremental_scores[arm_key] = self.arm_rewards[arm_key] / self.arm_spending[arm_key]
                    else:
                        # Unexplored - give benefit of doubt
                        incremental_scores[arm_key] = self._sample_beta(self.alpha[arm_key], self.beta[arm_key])
            
            # Reallocate based on incremental scores
            total_score = sum(max(0.1, s) for s in incremental_scores.values())
            remaining_budget = self.total_budget - self.total_spent
            
            if remaining_budget > 0 and total_score > 0:
                min_budget = remaining_budget * self.min_allocation
                
                for arm in self.arms:
                    arm_key = str(arm)
                    score = max(0.1, incremental_scores.get(arm_key, 0.1))
                    proportion = score / total_score
                    allocation[arm_key] = max(min_budget, remaining_budget * proportion)
        
        # Reserve holdout budget (not actually spent)
        holdout_budget = (self.total_budget - self.total_spent) * self.holdout_percentage
        
        # Scale down allocations to account for holdout
        scale_factor = 1.0 - self.holdout_percentage
        for arm_key in allocation:
            allocation[arm_key] *= scale_factor
        
        return allocation
    
    def get_incrementality_summary(self) -> dict:
        """
        Get summary of incrementality measurements and adjustments.
        
        Returns:
            Dictionary with incrementality metrics and adjustment history
        """
        holdout_metrics = self.holdout_arm.get_metrics()
        
        arm_incrementality = {}
        for arm in self.arms:
            arm_key = str(arm)
            observed_roas = self.arm_rewards[arm_key] / self.arm_spending[arm_key] if self.arm_spending[arm_key] > 0 else 0
            
            arm_incrementality[arm_key] = {
                'observed_roas': observed_roas,
                'incremental_roas': self.incrementality_priors.get(arm_key),
                'roas_inflation': self.observed_vs_incremental.get(arm_key, 1.0),
                'adjustment_applied': self.incrementality_adjustments_applied.get(arm_key, False),
                'current_allocation': self.current_allocation.get(arm_key, 0),
                'alpha': self.alpha[arm_key],
                'beta': self.beta[arm_key]
            }
        
        return {
            'holdout_metrics': holdout_metrics,
            'arm_incrementality': arm_incrementality,
            'adjustment_history': self.adjustment_history,
            'total_adjustments': len(self.adjustment_history)
        }
    
    def calculate_arm_incrementality(self, arm_key: str) -> dict:
        """
        Calculate incrementality for a specific arm using holdout data.
        
        Args:
            arm_key: String key for the arm
        
        Returns:
            Dictionary with incrementality metrics for this arm
        """
        from src.bandit_ads.incrementality import calculate_incrementality, calculate_incremental_roas
        
        # Get arm metrics
        arm_spending = self.arm_spending.get(arm_key, 0)
        arm_revenue = self.arm_rewards.get(arm_key, 0)
        arm_impressions = self.arm_impressions.get(arm_key, 0)
        
        # Get holdout metrics
        baseline_cvr = self.holdout_arm.get_baseline_cvr()
        baseline_rpu = self.holdout_arm.get_baseline_revenue_per_user()
        holdout_users = self.holdout_arm.organic_users
        holdout_conversions = self.holdout_arm.organic_conversions
        holdout_revenue = self.holdout_arm.organic_revenue
        
        # Estimate treatment metrics (users who saw this arm's ads)
        # This is a simplification - in production, you'd track this directly
        treatment_users = arm_impressions  # Approximate users = impressions
        
        if arm_spending > 0 and treatment_users > 0:
            # Calculate observed CVR for this arm
            # Note: In production, track actual conversions per arm
            observed_roas = arm_revenue / arm_spending if arm_spending > 0 else 0
            
            # Use holdout as control
            if holdout_users > 0:
                result = calculate_incremental_roas(
                    treatment_revenue=arm_revenue,
                    control_revenue=holdout_revenue,
                    treatment_spend=arm_spending,
                    treatment_users=treatment_users,
                    control_users=holdout_users
                )
                
                return {
                    'arm_key': arm_key,
                    'incremental_roas': result['incremental_roas'],
                    'observed_roas': result['observed_roas'],
                    'roas_inflation': result['roas_inflation'],
                    'incremental_revenue': result['incremental_revenue'],
                    'has_data': True
                }
        
        return {
            'arm_key': arm_key,
            'incremental_roas': None,
            'observed_roas': None,
            'roas_inflation': None,
            'incremental_revenue': None,
            'has_data': False
        }
    
    def _get_timestamp(self):
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def incorporate_meridian_posteriors(
        self, campaign_id=None
    ):
        """
        Update arm priors using Meridian posterior distributions.

        Loads a trained Meridian model, converts its media-coefficient posteriors
        to Beta(alpha, beta) via sigmoid + method-of-moments, and overwrites the
        current priors.  Forces a budget reallocation afterwards.

        Returns the number of arms updated.
        """
        try:
            from src.bandit_ads.meridian_bridge import update_bandit_from_meridian
            updated = update_bandit_from_meridian(self, campaign_id=campaign_id)
            if updated > 0:
                self.adjustment_history.append({
                    'direction': 'meridian_update',
                    'reason': 'meridian_posteriors_applied',
                    'arms_updated': updated,
                    'timestamp': self._get_timestamp(),
                })
            return updated
        except Exception as exc:
            from src.bandit_ads.utils import get_logger
            get_logger('agent').warning(
                f"Could not apply Meridian posteriors: {exc}"
            )
            return 0

    def get_performance_metrics(self):
        """
        Override to include incrementality metrics.
        """
        base_metrics = super().get_performance_metrics()

        # Add incrementality data
        base_metrics['incrementality'] = self.get_incrementality_summary()
        base_metrics['holdout_percentage'] = self.holdout_percentage

        return base_metrics