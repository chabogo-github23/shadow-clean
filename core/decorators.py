from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib.auth.models import AnonymousUser
from .models import PseudonymousUser, Project, AuditLog


def get_client_ip(request):
    """Extract client IP address for audit logging"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _get_user(request):
    """
    Safe helper to retrieve the user object.
    Always returns either a PseudonymousUser instance or None.
    """
    user = getattr(request, 'user', None)
    if isinstance(user, AnonymousUser) or user is None:
        return None
    return user


def pseudonymous_user_required(view_func):
    """Ensure pseudonymous session is active before allowing access"""
    def wrapper(request, *args, **kwargs):
        user_id = request.session.get('pseudonymous_user_id')
        if not user_id:
            return redirect('core:request_magic_link')

        try:
            user = PseudonymousUser.objects.get(id=user_id)
        except PseudonymousUser.DoesNotExist:
            request.session.pop('pseudonymous_user_id', None)
            return redirect('core:request_magic_link')

        # Attach pseudonymous user to request
        request.user = user
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Require pseudonymous user with is_admin=True"""
    def wrapper(request, *args, **kwargs):
        user = _get_user(request)
        if not user:
            return redirect('core:request_magic_link')

        if not getattr(user, 'is_admin', False):
            AuditLog.objects.create(
                user=user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'admin',
                    'user_has_admin': getattr(user, 'is_admin', None)
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Admin access required")

        return view_func(request, *args, **kwargs)
    return wrapper


def analyst_required(view_func):
    """Require pseudonymous user with is_analyst=True"""
    def wrapper(request, *args, **kwargs):
        user = _get_user(request)
        if not user:
            return redirect('core:request_magic_link')

        if not getattr(user, 'is_analyst', False):
            AuditLog.objects.create(
                user=user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'analyst',
                    'user_has_analyst': getattr(user, 'is_analyst', None)
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Analyst access required")

        return view_func(request, *args, **kwargs)
    return wrapper


def client_required(view_func):
    """Require pseudonymous user who is NOT admin or analyst"""
    def wrapper(request, *args, **kwargs):
        user = _get_user(request)
        if not user:
            return redirect('core:request_magic_link')

        if getattr(user, 'is_admin', False) or getattr(user, 'is_analyst', False):
            AuditLog.objects.create(
                user=user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'client',
                    'user_is_admin': getattr(user, 'is_admin', None),
                    'user_is_analyst': getattr(user, 'is_analyst', None)
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Client access only")

        return view_func(request, *args, **kwargs)
    return wrapper


def project_access_required(view_func):
    """Ensure pseudonymous user has access to the given project"""
    def wrapper(request, project_id, *args, **kwargs):
        user = _get_user(request)
        if not user:
            return redirect('core:request_magic_link')

        try:
            from django.core.exceptions import ValidationError
            import uuid

            try:
                project_id = uuid.UUID(project_id)
            except (ValueError, AttributeError):
                return HttpResponseForbidden("Invalid project ID")

            project = Project.objects.get(id=project_id)

            has_access = (
                project.client == user or
                getattr(user, 'is_admin', False) or
                getattr(user, 'is_analyst', False)
            )

            if not has_access:
                AuditLog.objects.create(
                    user=user,
                    project=project,
                    action='unauthorized_project_access',
                    details={
                        'project_id': str(project.id),
                        'project_client': str(project.client.id),
                        'attempted_user': str(user.id)
                    },
                    ip_address=get_client_ip(request)
                )
                return HttpResponseForbidden("Project access denied")

        except Project.DoesNotExist:
            return HttpResponseForbidden("Project not found")
        except ValidationError as e:
            return HttpResponseForbidden(f"Invalid project ID: {e}")

        request.project = project
        return view_func(request, *args, **kwargs)
    return wrapper


def analyst_project_access_required(view_func):
    """Require pseudonymous user to be assigned analyst for project or admin"""
    def wrapper(request, project_id, *args, **kwargs):
        user = _get_user(request)
        if not user:
            return redirect('core:request_magic_link')

        if not getattr(user, 'is_analyst', False) and not getattr(user, 'is_admin', False):
            return HttpResponseForbidden("Analyst or admin access required")

        try:
            import uuid
            try:
                project_id = uuid.UUID(project_id)
            except (ValueError, AttributeError):
                return HttpResponseForbidden("Invalid project ID")

            project = Project.objects.get(id=project_id)

            has_access = (
                project.assigned_analyst == user or
                getattr(user, 'is_admin', False)
            )

            if not has_access:
                AuditLog.objects.create(
                    user=user,
                    project=project,
                    action='unauthorized_analyst_access',
                    details={
                        'project_id': str(project.id),
                        'assigned_analyst': str(project.assigned_analyst.id)
                        if project.assigned_analyst else None,
                        'attempted_analyst': str(user.id)
                    },
                    ip_address=get_client_ip(request)
                )
                return HttpResponseForbidden("Not assigned to this project")

        except Project.DoesNotExist:
            return HttpResponseForbidden("Project not found")

        request.project = project
        return view_func(request, *args, **kwargs)
    return wrapper
