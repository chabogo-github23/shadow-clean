from django.utils.deprecation import MiddlewareMixin
from .models import PseudonymousUser

class PseudonymousAuthMiddleware(MiddlewareMixin):
    """Middleware to attach current user to request"""
    
    def process_request(self, request):
        user_id = request.session.get('user_id')
        if user_id:
            try:
                request.user_obj = PseudonymousUser.objects.get(id=user_id)
            except PseudonymousUser.DoesNotExist:
                request.user_obj = None
        else:
            request.user_obj = None
        return None
