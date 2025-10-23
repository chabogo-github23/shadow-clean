from .models import PseudonymousUser
from django.utils import timezone

class PseudonymousAuthMiddleware:
    """Attach pseudonymous user from session to request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.session.get('pseudonymous_user_id')

        if user_id:
            try:
                user = PseudonymousUser.objects.get(id=user_id)
                request.user = user
                user.last_seen = timezone.now()
                user.save(update_fields=['last_seen'])
            except PseudonymousUser.DoesNotExist:
                request.user = None
        else:
            request.user = None

        response = self.get_response(request)
        return response
