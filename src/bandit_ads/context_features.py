"""
Context feature extraction and encoding for contextual bandits.

Supports user demographics, temporal features, device info, and custom features.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib


class ContextFeatureExtractor:
    """
    Extracts and encodes contextual features for bandit learning.
    
    Features include:
    - User demographics (age, gender, location)
    - Temporal features (time-of-day, day-of-week, season)
    - Device information (device type, OS)
    - Custom features (user segments, behavior)
    """
    
    def __init__(self, feature_config: Optional[Dict[str, Any]] = None):
        """
        Initialize feature extractor with configuration.
        
        Args:
            feature_config: Dictionary specifying which features to include
                Example:
                {
                    'demographics': ['age_group', 'gender', 'location'],
                    'temporal': ['hour', 'day_of_week', 'month'],
                    'device': ['device_type', 'os'],
                    'custom': ['user_segment', 'purchase_history']
                }
        """
        self.config = feature_config or self._default_config()
        self.feature_names = self._build_feature_names()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default feature configuration."""
        return {
            'demographics': {
                'age_group': True,
                'gender': True,
                'location': True
            },
            'temporal': {
                'hour': True,
                'day_of_week': True,
                'month': True,
                'is_weekend': True
            },
            'device': {
                'device_type': True,
                'os': False  # Disabled by default
            },
            'custom': {}  # User-defined features
        }
    
    def _build_feature_names(self) -> List[str]:
        """Build list of all feature names for encoding."""
        names = []
        
        # Demographics
        if self.config.get('demographics', {}).get('age_group'):
            names.extend([f'age_{g}' for g in ['18-24', '25-34', '35-44', '45-54', '55+']])
        if self.config.get('demographics', {}).get('gender'):
            names.extend(['gender_male', 'gender_female', 'gender_other'])
        if self.config.get('demographics', {}).get('location'):
            names.extend(['location_us', 'location_eu', 'location_asia', 'location_other'])
        
        # Temporal
        if self.config.get('temporal', {}).get('hour'):
            names.extend([f'hour_{i}' for i in range(24)])
        if self.config.get('temporal', {}).get('day_of_week'):
            names.extend([f'day_{i}' for i in range(7)])
        if self.config.get('temporal', {}).get('month'):
            names.extend([f'month_{i}' for i in range(12)])
        if self.config.get('temporal', {}).get('is_weekend'):
            names.append('is_weekend')
        
        # Device
        if self.config.get('device', {}).get('device_type'):
            names.extend(['device_mobile', 'device_desktop', 'device_tablet'])
        if self.config.get('device', {}).get('os'):
            names.extend(['os_ios', 'os_android', 'os_windows', 'os_mac', 'os_other'])
        
        # Custom features (user-defined)
        custom_config = self.config.get('custom', {})
        for feature_name, feature_values in custom_config.items():
            if isinstance(feature_values, list):
                names.extend([f'{feature_name}_{v}' for v in feature_values])
            else:
                names.append(feature_name)
        
        return names
    
    def extract_context(self, user_data: Optional[Dict[str, Any]] = None, 
                       timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Extract context features from user data and timestamp.
        
        Args:
            user_data: Dictionary with user information:
                {
                    'age': int or 'age_group': str,
                    'gender': str,
                    'location': str,
                    'device_type': str,
                    'os': str,
                    ... (custom features)
                }
            timestamp: Datetime object (defaults to now)
        
        Returns:
            Dictionary with context features
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        context = {}
        
        # Demographics
        if user_data:
            # Age group
            if self.config.get('demographics', {}).get('age_group'):
                age = user_data.get('age') or user_data.get('age_group')
                if isinstance(age, int):
                    age_group = self._age_to_group(age)
                else:
                    age_group = age or '25-34'  # Default
                for group in ['18-24', '25-34', '35-44', '45-54', '55+']:
                    context[f'age_{group}'] = 1.0 if group == age_group else 0.0
            
            # Gender
            if self.config.get('demographics', {}).get('gender'):
                gender = user_data.get('gender', 'other').lower()
                context['gender_male'] = 1.0 if gender == 'male' else 0.0
                context['gender_female'] = 1.0 if gender == 'female' else 0.0
                context['gender_other'] = 1.0 if gender not in ['male', 'female'] else 0.0
            
            # Location
            if self.config.get('demographics', {}).get('location'):
                location = user_data.get('location', 'other').lower()
                context['location_us'] = 1.0 if location in ['us', 'usa', 'united states'] else 0.0
                context['location_eu'] = 1.0 if location in ['eu', 'europe'] else 0.0
                context['location_asia'] = 1.0 if location in ['asia', 'as'] else 0.0
                context['location_other'] = 1.0 if not any([context['location_us'], 
                                                             context['location_eu'], 
                                                             context['location_asia']]) else 0.0
        
        # Temporal features
        if self.config.get('temporal', {}).get('hour'):
            hour = timestamp.hour
            for i in range(24):
                context[f'hour_{i}'] = 1.0 if i == hour else 0.0
        
        if self.config.get('temporal', {}).get('day_of_week'):
            day = timestamp.weekday()  # 0=Monday, 6=Sunday
            for i in range(7):
                context[f'day_{i}'] = 1.0 if i == day else 0.0
        
        if self.config.get('temporal', {}).get('month'):
            month = timestamp.month - 1  # 0-11
            for i in range(12):
                context[f'month_{i}'] = 1.0 if i == month else 0.0
        
        if self.config.get('temporal', {}).get('is_weekend'):
            context['is_weekend'] = 1.0 if timestamp.weekday() >= 5 else 0.0
        
        # Device features
        if user_data:
            if self.config.get('device', {}).get('device_type'):
                device = user_data.get('device_type', 'desktop').lower()
                context['device_mobile'] = 1.0 if device == 'mobile' else 0.0
                context['device_desktop'] = 1.0 if device == 'desktop' else 0.0
                context['device_tablet'] = 1.0 if device == 'tablet' else 0.0
            
            if self.config.get('device', {}).get('os'):
                os_type = user_data.get('os', 'other').lower()
                context['os_ios'] = 1.0 if 'ios' in os_type or 'iphone' in os_type else 0.0
                context['os_android'] = 1.0 if 'android' in os_type else 0.0
                context['os_windows'] = 1.0 if 'windows' in os_type else 0.0
                context['os_mac'] = 1.0 if 'mac' in os_type or 'macos' in os_type else 0.0
                context['os_other'] = 1.0 if not any([context['os_ios'], context['os_android'], 
                                                      context['os_windows'], context['os_mac']]) else 0.0
        
        # Custom features
        custom_config = self.config.get('custom', {})
        for feature_name, feature_values in custom_config.items():
            if feature_name in (user_data or {}):
                value = user_data[feature_name]
                if isinstance(feature_values, list):
                    # One-hot encoding
                    for v in feature_values:
                        context[f'{feature_name}_{v}'] = 1.0 if value == v else 0.0
                else:
                    # Binary or numeric
                    context[feature_name] = float(value) if isinstance(value, (int, float)) else 1.0
        
        return context
    
    def encode_context_vector(self, context: Dict[str, Any]) -> List[float]:
        """
        Encode context dictionary as a feature vector.
        
        Args:
            context: Context dictionary from extract_context()
        
        Returns:
            List of feature values in the order of feature_names
        """
        return [context.get(name, 0.0) for name in self.feature_names]
    
    def _age_to_group(self, age: int) -> str:
        """Convert age to age group."""
        if age < 25:
            return '18-24'
        elif age < 35:
            return '25-34'
        elif age < 45:
            return '35-44'
        elif age < 55:
            return '45-54'
        else:
            return '55+'
    
    def get_feature_dimension(self) -> int:
        """Get the dimension of the context feature vector."""
        return len(self.feature_names)
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        return self.feature_names.copy()


def create_default_context(user_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to create a default context.
    
    Args:
        user_data: Optional user data dictionary
    
    Returns:
        Context dictionary
    """
    extractor = ContextFeatureExtractor()
    return extractor.extract_context(user_data=user_data)
