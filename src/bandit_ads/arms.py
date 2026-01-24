class Arm:
    """
    Represents a single ad option (arm) in the bandit.
    """
    def __init__(self, platform, channel, creative, bid):
        self.platform = platform
        self.channel = channel
        self.creative = creative
        self.bid = bid

    def __repr__(self):
        return f"Arm(platform={self.platform}, channel={self.channel}, creative={self.creative}, bid={self.bid})"


class ArmManager:
    """
    Manages all possible arms in the campaign.
    """
    def __init__(self, platforms, channels, creatives, bids):
        self.arms = []
        for platform in platforms:
            for channel in channels:
                for creative in creatives:
                    for bid in bids:
                        self.arms.append(Arm(platform, channel, creative, bid))

    def get_arms(self):
        return self.arms
