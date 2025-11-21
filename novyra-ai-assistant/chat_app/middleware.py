"""Middleware for tracking user logins"""
import re
from django.utils import timezone
from django.conf import settings
from .models import LoginHistory, UserProfile


class LoginTrackingMiddleware:
    """Track user logins and create user profiles"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Track login if user is authenticated
        if request.user.is_authenticated:
            session_key = request.session.session_key
            if session_key:
                # Check if this is a new login (no recent login history for this session)
                recent_login = LoginHistory.objects.filter(
                    user=request.user,
                    session_key=session_key,
                    logout_time__isnull=True
                ).first()
                
                if not recent_login:
                    # New login - create login history
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    ip_address = self.get_client_ip(request)
                    device, browser = self.parse_user_agent(user_agent)
                    
                    LoginHistory.objects.create(
                        user=request.user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        device=device,
                        browser=browser,
                        session_key=session_key
                    )
                    
                    # Create user profile if it doesn't exist
                    UserProfile.objects.get_or_create(user=request.user)
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def parse_user_agent(self, user_agent):
        """Parse user agent to extract device and browser"""
        device = 'Unknown'
        browser = 'Unknown'
        
        if user_agent:
            # Detect device
            if 'Mobile' in user_agent or 'Android' in user_agent:
                device = 'Mobile'
            elif 'Tablet' in user_agent or 'iPad' in user_agent:
                device = 'Tablet'
            elif 'Windows' in user_agent:
                device = 'Windows'
            elif 'Mac' in user_agent:
                device = 'Mac'
            elif 'Linux' in user_agent:
                device = 'Linux'
            
            # Detect browser
            if 'Chrome' in user_agent and 'Edg' not in user_agent:
                browser = 'Chrome'
            elif 'Firefox' in user_agent:
                browser = 'Firefox'
            elif 'Safari' in user_agent and 'Chrome' not in user_agent:
                browser = 'Safari'
            elif 'Edg' in user_agent:
                browser = 'Edge'
            elif 'Opera' in user_agent:
                browser = 'Opera'
        
        return device, browser
