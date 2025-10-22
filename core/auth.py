import secrets
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import PseudonymousUser

def generate_magic_token():
    """Generate a secure magic token"""
    return secrets.token_urlsafe(32)

def send_magic_link(user, request):
    """Send magic link email to user"""
    token = generate_magic_token()
    expires = timezone.now() + timedelta(hours=24)
    
    user.magic_token = token
    user.magic_token_expires = expires
    user.save()
    
    # Build magic link
    protocol = 'https' if request.is_secure() else 'http'
    domain = request.get_host()
    magic_link = f"{protocol}://{domain}/auth/verify/{token}/"
    
    # Send email
    subject = "Your ShadowIQ Magic Link"
    message = f"""
    Hello {user.alias},
    
    Click the link below to access your ShadowIQ account:
    {magic_link}
    
    This link expires in 24 hours.
    
    If you didn't request this link, please ignore this email.
    
    Best regards,
    ShadowIQ Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending magic link: {e}")
        return False

def verify_magic_token(token):
    """Verify magic token and return user if valid"""
    try:
        user = PseudonymousUser.objects.get(magic_token=token)
        
        # Check if token expired
        if user.magic_token_expires < timezone.now():
            return None
        
        # Clear token and update last login
        user.magic_token = None
        user.magic_token_expires = None
        user.last_login = timezone.now()
        user.save()
        
        return user
    except PseudonymousUser.DoesNotExist:
        return None

def get_or_create_pseudonymous_user(alias, email=None):
    """Get or create a pseudonymous user"""
    user, created = PseudonymousUser.objects.get_or_create(
        alias=alias,
        defaults={'email': email}
    )
    return user, created
