import random

class AdEnvironment:
    """
    Simulates an advertising environment. Returns reward metrics for a given arm.
    """

    def __init__(self, arm_params=None):
        """
        arm_params: optional dictionary to configure CTR, CVR, revenue, cost for each arm type.
        """
        self.arm_params = arm_params or {}

    def step(self, arm):
        """
        Simulate one round of serving an ad (pulling the arm).
        Returns a dictionary with metrics and reward (ROAS).
        """
        # For simplicity, generate random CTR, CVR, revenue per conversion
        ctr = self.arm_params.get("ctr", 0.05)  # default 5% click-through rate
        cvr = self.arm_params.get("cvr", 0.1)   # default 10% conversion rate
        revenue_per_conversion = self.arm_params.get("revenue", 10.0)
        cost_per_click = self.arm_params.get("cpc", 1.0)

        clicks = int(random.random() < ctr)  # simple binary outcome per impression (Bernoulli trial)
        conversions = clicks * int(random.random() < cvr)
        revenue = conversions * revenue_per_conversion
        cost = clicks * cost_per_click
        roas = revenue / cost if cost > 0 else 0.0

        return {
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "cost": cost,
            "roas": roas
        }
