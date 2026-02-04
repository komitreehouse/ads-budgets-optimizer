"""
Webhook handlers for receiving real-time events from advertising platforms.

Supports webhooks from Google Ads, Meta Ads, and The Trade Desk.
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from flask import Flask, request, jsonify, abort

from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    get_campaign_by_name, get_arm_by_attributes,
    create_metric, log_api_call, get_arm_platform_entity_ids,
    get_arms_by_campaign, get_arm
)
from src.bandit_ads.database import get_db_manager
from sqlalchemy import and_
from src.bandit_ads.models import MetricCreate
from src.bandit_ads.utils import get_logger

logger = get_logger('webhooks')

app = Flask(__name__)


class WebhookHandler:
    """Handles webhook events from advertising platforms."""
    
    def __init__(self, secret_keys: Optional[Dict[str, str]] = None):
        """
        Initialize webhook handler.
        
        Args:
            secret_keys: Dictionary of platform -> secret key for signature verification
        """
        self.secret_keys = secret_keys or {}
        self.handlers: Dict[str, Callable] = {}
        logger.info("Webhook handler initialized")
    
    def register_handler(self, platform: str, handler: Callable):
        """Register a handler function for a platform."""
        self.handlers[platform.lower()] = handler
        logger.info(f"Registered handler for platform: {platform}")
    
    def verify_signature(self, platform: str, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            platform: Platform name
            payload: Raw request payload
            signature: Signature from request headers (may include prefix like 'sha256=')
        """
        if platform not in self.secret_keys:
            logger.warning(f"No secret key configured for {platform}, skipping verification")
            return True  # Allow if no secret configured
        
        secret = self.secret_keys[platform].encode('utf-8')
        
        # Platform-specific signature verification
        platform_lower = platform.lower()
        
        if platform_lower in ['meta', 'facebook']:
            # Meta uses 'sha256=' prefix
            if signature.startswith('sha256='):
                signature = signature[7:]
            expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        elif platform_lower in ['google', 'google_ads']:
            # Google Ads typically uses SHA256 HMAC
            expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        elif platform_lower in ['trade_desk', 'ttd', 'the_trade_desk']:
            # TTD uses SHA256 HMAC
            expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        else:
            # Default to SHA256
            expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)
    
    def _find_arm_by_platform_entity_id(self, campaign_id: int, platform: str, 
                                       platform_entity_id: str, entity_type: str = 'campaign_id') -> Optional[Any]:
        """
        Find arm by platform entity ID (e.g., Google Ads campaign_id, ad_group_id).
        
        Args:
            campaign_id: Campaign ID in our database
            platform: Platform name
            platform_entity_id: Platform-specific entity ID
            entity_type: Type of entity ID (campaign_id, ad_group_id, keyword_id, etc.)
        """
        from src.bandit_ads.database import Arm as DBArm
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            arms = session.query(DBArm).filter(
                and_(
                    DBArm.campaign_id == campaign_id,
                    DBArm.platform == platform
                )
            ).all()
            
            # Check each arm's platform_entity_ids
            for arm in arms:
                if arm.platform_entity_ids:
                    try:
                        import json
                        entity_ids = json.loads(arm.platform_entity_ids)
                        if entity_ids.get(entity_type) == platform_entity_id:
                            return arm
                    except (json.JSONDecodeError, TypeError):
                        continue
        return None
    
    def handle_google_ads_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Ads conversion webhook."""
        try:
            # Parse Google Ads webhook format
            # Google Ads webhooks can include conversion data with campaign/ad group IDs
            conversion_data = data.get('conversion', {}) or data
            
            # Try to get campaign by platform entity ID first
            google_campaign_id = conversion_data.get('campaign_id') or conversion_data.get('CampaignId')
            campaign_name = conversion_data.get('campaign_name') or conversion_data.get('CampaignName')
            platform = 'Google'
            
            campaign = None
            if campaign_name:
                campaign = get_campaign_by_name(campaign_name)
            
            # If campaign not found by name, try to find by platform entity ID
            if not campaign and google_campaign_id:
                # Search all campaigns' arms for matching platform_entity_ids
                from src.bandit_ads.database import Campaign, Arm as DBArm
                import json
                db_manager = get_db_manager()
                with db_manager.get_session() as session:
                    # Find arm with matching Google campaign_id
                    arms = session.query(DBArm).filter(
                        DBArm.platform == platform
                    ).all()
                    
                    for arm in arms:
                        if arm.platform_entity_ids:
                            try:
                                entity_ids = json.loads(arm.platform_entity_ids)
                                if entity_ids.get('campaign_id') == str(google_campaign_id):
                                    campaign = session.query(Campaign).filter(Campaign.id == arm.campaign_id).first()
                                    break
                            except (json.JSONDecodeError, TypeError):
                                continue
            
            if not campaign:
                logger.warning(f"Campaign not found for Google Ads webhook: {campaign_name or google_campaign_id}")
                return {'success': False, 'error': 'Campaign not found'}
            
            # Try to find arm by platform entity IDs first
            arm = None
            google_ad_group_id = conversion_data.get('ad_group_id') or conversion_data.get('AdGroupId')
            google_keyword_id = conversion_data.get('keyword_id') or conversion_data.get('KeywordId')
            
            if google_keyword_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, google_keyword_id, 'keyword_id')
            elif google_ad_group_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, google_ad_group_id, 'ad_group_id')
            elif google_campaign_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, google_campaign_id, 'campaign_id')
            
            # Fallback to attribute matching
            if not arm:
                channel = conversion_data.get('channel', 'Search')
                creative = conversion_data.get('creative', 'Unknown')
                bid = float(conversion_data.get('bid', 1.0))
                
                arm = get_arm_by_attributes(
                    campaign.id, platform, channel, creative, bid
                )
            
            if not arm:
                logger.warning(f"Arm not found for Google Ads webhook")
                return {'success': False, 'error': 'Arm not found'}
            
            # Create metric
            metric = create_metric(MetricCreate(
                campaign_id=campaign.id,
                arm_id=arm.id,
                timestamp=datetime.utcnow(),
                impressions=conversion_data.get('impressions', 0),
                clicks=conversion_data.get('clicks', 0),
                conversions=conversion_data.get('conversions', 1),  # Webhook usually means conversion
                revenue=conversion_data.get('revenue', 0.0),
                cost=conversion_data.get('cost', 0.0),
                source='webhook'
            ))
            
            logger.info(f"Processed Google Ads webhook: {conversion_data.get('conversions', 0)} conversions")
            return {'success': True, 'metric_id': metric.id}
            
        except Exception as e:
            logger.error(f"Error handling Google Ads webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def handle_meta_ads_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Meta Ads conversion webhook."""
        try:
            # Parse Meta Ads webhook format
            # Meta webhooks can have different structures
            entry = data.get('entry', [{}])
            if entry:
                changes = entry[0].get('changes', [{}])
                if changes:
                    value = changes[0].get('value', {})
                else:
                    value = entry[0]
            else:
                value = data
            
            # Try to get platform entity IDs
            meta_campaign_id = value.get('campaign_id') or value.get('id')
            meta_ad_set_id = value.get('adset_id') or value.get('ad_set_id')
            meta_ad_id = value.get('ad_id')
            campaign_name = value.get('campaign_name') or value.get('name')
            platform = 'Meta'
            
            campaign = None
            if campaign_name:
                campaign = get_campaign_by_name(campaign_name)
            
            # If campaign not found by name, try to find by platform entity ID
            if not campaign and meta_campaign_id:
                from src.bandit_ads.database import Campaign, Arm as DBArm
                import json
                db_manager = get_db_manager()
                with db_manager.get_session() as session:
                    arms = session.query(DBArm).filter(
                        DBArm.platform == platform
                    ).all()
                    
                    for arm in arms:
                        if arm.platform_entity_ids:
                            try:
                                entity_ids = json.loads(arm.platform_entity_ids)
                                if entity_ids.get('campaign_id') == str(meta_campaign_id):
                                    campaign = session.query(Campaign).filter(Campaign.id == arm.campaign_id).first()
                                    break
                            except (json.JSONDecodeError, TypeError):
                                continue
            
            if not campaign:
                logger.warning(f"Campaign not found for Meta Ads webhook: {campaign_name or meta_campaign_id}")
                return {'success': False, 'error': 'Campaign not found'}
            
            # Try to find arm by platform entity IDs first
            arm = None
            if meta_ad_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, meta_ad_id, 'ad_id')
            elif meta_ad_set_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, meta_ad_set_id, 'ad_set_id')
            elif meta_campaign_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, meta_campaign_id, 'campaign_id')
            
            # Fallback to attribute matching
            if not arm:
                channel = value.get('channel', 'Social')
                creative = value.get('creative', 'Unknown')
                bid = float(value.get('bid', 1.0))
                
                arm = get_arm_by_attributes(
                    campaign.id, platform, channel, creative, bid
                )
            
            if not arm:
                logger.warning(f"Arm not found for Meta Ads webhook")
                return {'success': False, 'error': 'Arm not found'}
            
            # Create metric
            metric = create_metric(MetricCreate(
                campaign_id=campaign.id,
                arm_id=arm.id,
                timestamp=datetime.utcnow(),
                impressions=value.get('impressions', 0),
                clicks=value.get('clicks', 0),
                conversions=value.get('conversions', 1),
                revenue=value.get('revenue', 0.0),
                cost=value.get('cost', 0.0) or value.get('spend', 0.0),
                source='webhook'
            ))
            
            logger.info(f"Processed Meta Ads webhook: {value.get('conversions', 0)} conversions")
            return {'success': True, 'metric_id': metric.id}
            
        except Exception as e:
            logger.error(f"Error handling Meta Ads webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def handle_trade_desk_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle The Trade Desk event webhook."""
        try:
            # Parse The Trade Desk webhook format
            event_data = data.get('event', {}) or data
            ttd_campaign_id = event_data.get('CampaignId') or event_data.get('campaign_id')
            ttd_strategy_id = event_data.get('StrategyId') or event_data.get('strategy_id')
            ttd_ad_group_id = event_data.get('AdGroupId') or event_data.get('ad_group_id')
            campaign_name = event_data.get('CampaignName') or event_data.get('campaign_name')
            platform = 'The Trade Desk'
            
            campaign = None
            if campaign_name:
                campaign = get_campaign_by_name(campaign_name)
            
            # If campaign not found by name, try to find by platform entity ID
            if not campaign and ttd_campaign_id:
                from src.bandit_ads.database import Campaign, Arm as DBArm
                import json
                db_manager = get_db_manager()
                with db_manager.get_session() as session:
                    arms = session.query(DBArm).filter(
                        DBArm.platform == platform
                    ).all()
                    
                    for arm in arms:
                        if arm.platform_entity_ids:
                            try:
                                entity_ids = json.loads(arm.platform_entity_ids)
                                if entity_ids.get('campaign_id') == str(ttd_campaign_id):
                                    campaign = session.query(Campaign).filter(Campaign.id == arm.campaign_id).first()
                                    break
                            except (json.JSONDecodeError, TypeError):
                                continue
            
            if not campaign:
                logger.warning(f"Campaign not found for TTD webhook: {campaign_name or ttd_campaign_id}")
                return {'success': False, 'error': 'Campaign not found'}
            
            # Try to find arm by platform entity IDs first
            arm = None
            if ttd_strategy_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, ttd_strategy_id, 'strategy_id')
            elif ttd_ad_group_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, ttd_ad_group_id, 'ad_group_id')
            elif ttd_campaign_id:
                arm = self._find_arm_by_platform_entity_id(campaign.id, platform, ttd_campaign_id, 'campaign_id')
            
            # Fallback to attribute matching
            if not arm:
                channel = event_data.get('channel', 'Display')
                creative = event_data.get('creative', 'Unknown')
                bid = float(event_data.get('bid', 1.0))
                
                arm = get_arm_by_attributes(
                    campaign.id, platform, channel, creative, bid
                )
            
            if not arm:
                logger.warning(f"Arm not found for TTD webhook")
                return {'success': False, 'error': 'Arm not found'}
            
            # Create metric
            metric = create_metric(MetricCreate(
                campaign_id=campaign.id,
                arm_id=arm.id,
                timestamp=datetime.utcnow(),
                impressions=event_data.get('Impressions', 0) or event_data.get('impressions', 0),
                clicks=event_data.get('Clicks', 0) or event_data.get('clicks', 0),
                conversions=event_data.get('Conversions', 1) or event_data.get('conversions', 1),
                revenue=event_data.get('Revenue', 0.0) or event_data.get('revenue', 0.0),
                cost=event_data.get('Spend', 0.0) or event_data.get('cost', 0.0),
                source='webhook'
            ))
            
            logger.info(f"Processed The Trade Desk webhook: {event_data.get('conversions', 0) or event_data.get('Conversions', 0)} conversions")
            return {'success': True, 'metric_id': metric.id}
            
        except Exception as e:
            logger.error(f"Error handling The Trade Desk webhook: {str(e)}")
            return {'success': False, 'error': str(e)}


# Global webhook handler instance
_webhook_handler: Optional[WebhookHandler] = None


def get_webhook_handler(secret_keys: Optional[Dict[str, str]] = None) -> WebhookHandler:
    """Get or create the global webhook handler."""
    global _webhook_handler
    if _webhook_handler is None:
        _webhook_handler = WebhookHandler(secret_keys)
        # Register default handlers
        _webhook_handler.register_handler('google', _webhook_handler.handle_google_ads_webhook)
        _webhook_handler.register_handler('meta', _webhook_handler.handle_meta_ads_webhook)
        _webhook_handler.register_handler('trade_desk', _webhook_handler.handle_trade_desk_webhook)
    return _webhook_handler


# Flask routes
@app.route('/webhook/google', methods=['POST'])
def google_webhook():
    """Handle Google Ads webhook."""
    handler = get_webhook_handler()
    
    # Verify signature if configured
    signature = request.headers.get('X-Google-Signature')
    if signature and not handler.verify_signature('google', request.data, signature):
        abort(401, 'Invalid signature')
    
    data = request.get_json()
    result = handler.handle_google_ads_webhook(data)
    
    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/webhook/meta', methods=['POST'])
def meta_webhook():
    """Handle Meta Ads webhook."""
    handler = get_webhook_handler()
    
    # Verify signature if configured
    # Meta sends signature in X-Hub-Signature-256 header with 'sha256=' prefix
    signature = request.headers.get('X-Hub-Signature-256') or request.headers.get('X-Hub-Signature')
    if signature:
        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]
        if not handler.verify_signature('meta', request.data, signature):
            abort(401, 'Invalid signature')
    
    data = request.get_json()
    result = handler.handle_meta_ads_webhook(data)
    
    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/webhook/trade_desk', methods=['POST'])
def trade_desk_webhook():
    """Handle The Trade Desk webhook."""
    handler = get_webhook_handler()
    
    # Verify signature if configured
    signature = request.headers.get('X-Trade-Desk-Signature')
    if signature and not handler.verify_signature('trade_desk', request.data, signature):
        abort(401, 'Invalid signature')
    
    data = request.get_json()
    result = handler.handle_trade_desk_webhook(data)
    
    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/webhook/health', methods=['GET'])
def webhook_health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200


def run_webhook_server(host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
    """Run the webhook server."""
    logger.info(f"Starting webhook server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
