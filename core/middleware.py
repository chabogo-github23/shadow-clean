from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from .models import PseudonymousUser

class PseudonymousAuthMiddleware:
    """Middleware to attach pseudonymous user from session to the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = None
        user_id = request.session.get('pseudonymous_user_id')

        if user_id:
            try:
                user = PseudonymousUser.objects.get(id=user_id)
                # Update last seen timestamp
                user.last_seen = timezone.now()
                user.save(update_fields=['last_seen'])
            except PseudonymousUser.DoesNotExist:
                # Session refers to invalid user — clear it
                request.session.pop('pseudonymous_user_id', None)

        # Always assign a valid user-like object to request.user
        request.user = user if user else AnonymousUser()

        response = self.get_response(request)
        return response
