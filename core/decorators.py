# core/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect


def require_auth(view_func):
    """Decorator to ensure user is authenticated (e.g., logged in or has user_obj)"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user_obj exists and is authenticated
        if not hasattr(request, "user_obj") or request.user_obj is None:
            if request.headers.get("Accept") == "application/json":
                return JsonResponse({'error': 'Authentication required'}, status=401)
            return redirect('login')  # or your login page
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin(view_func):
    """Decorator to ensure the current user has admin privileges"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, "user_obj", None)
        if not user or not getattr(user, "is_admin", False):
            if request.headers.get("Accept") == "application/json":
                return JsonResponse({'error': 'Admin privileges required'}, status=403)
            return redirect('access_denied')  # optional custom template
        return view_func(request, *args, **kwargs)
    return wrapper
