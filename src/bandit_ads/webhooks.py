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
    create_metric, log_api_call
)
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
            signature: Signature from request headers
        """
        if platform not in self.secret_keys:
            logger.warning(f"No secret key configured for {platform}, skipping verification")
            return True  # Allow if no secret configured
        
        secret = self.secret_keys[platform].encode('utf-8')
        expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)
    
    def handle_google_ads_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Ads conversion webhook."""
        try:
            # Parse Google Ads webhook format
            # This is a simplified example - actual format may vary
            conversion_data = data.get('conversion', {})
            campaign_name = conversion_data.get('campaign_name')
            platform = conversion_data.get('platform', 'Google')
            channel = conversion_data.get('channel', 'Search')
            creative = conversion_data.get('creative', 'Unknown')
            bid = float(conversion_data.get('bid', 1.0))
            
            # Get campaign and arm
            campaign = get_campaign_by_name(campaign_name)
            if not campaign:
                logger.warning(f"Campaign not found: {campaign_name}")
                return {'success': False, 'error': 'Campaign not found'}
            
            arm = get_arm_by_attributes(
                campaign.id, platform, channel, creative, bid
            )
            if not arm:
                logger.warning(f"Arm not found: {platform}/{channel}/{creative}/{bid}")
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
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            
            campaign_name = value.get('campaign_name')
            platform = 'Meta'
            channel = value.get('channel', 'Social')
            creative = value.get('creative', 'Unknown')
            bid = float(value.get('bid', 1.0))
            
            # Get campaign and arm
            campaign = get_campaign_by_name(campaign_name)
            if not campaign:
                logger.warning(f"Campaign not found: {campaign_name}")
                return {'success': False, 'error': 'Campaign not found'}
            
            arm = get_arm_by_attributes(
                campaign.id, platform, channel, creative, bid
            )
            if not arm:
                logger.warning(f"Arm not found: {platform}/{channel}/{creative}/{bid}")
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
                cost=value.get('cost', 0.0),
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
            event_data = data.get('event', {})
            campaign_name = event_data.get('campaign_name')
            platform = 'The Trade Desk'
            channel = event_data.get('channel', 'Display')
            creative = event_data.get('creative', 'Unknown')
            bid = float(event_data.get('bid', 1.0))
            
            # Get campaign and arm
            campaign = get_campaign_by_name(campaign_name)
            if not campaign:
                logger.warning(f"Campaign not found: {campaign_name}")
                return {'success': False, 'error': 'Campaign not found'}
            
            arm = get_arm_by_attributes(
                campaign.id, platform, channel, creative, bid
            )
            if not arm:
                logger.warning(f"Arm not found: {platform}/{channel}/{creative}/{bid}")
                return {'success': False, 'error': 'Arm not found'}
            
            # Create metric
            metric = create_metric(MetricCreate(
                campaign_id=campaign.id,
                arm_id=arm.id,
                timestamp=datetime.utcnow(),
                impressions=event_data.get('impressions', 0),
                clicks=event_data.get('clicks', 0),
                conversions=event_data.get('conversions', 1),
                revenue=event_data.get('revenue', 0.0),
                cost=event_data.get('cost', 0.0),
                source='webhook'
            ))
            
            logger.info(f"Processed The Trade Desk webhook: {event_data.get('conversions', 0)} conversions")
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
    signature = request.headers.get('X-Hub-Signature-256')
    if signature and not handler.verify_signature('meta', request.data, signature):
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
