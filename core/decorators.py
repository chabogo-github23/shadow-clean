from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib.auth import logout
from .models import PseudonymousUser, Project, AuditLog


def get_client_ip(request):
    """Extract client IP address for audit logging"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def pseudonymous_user_required(view_func):
    """Ensure pseudonymous session is active"""
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
    """Require user to have is_admin = True"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:request_magic_link')  # ADDED core:
            
        if not request.user.is_admin:
            AuditLog.objects.create(
                user=request.user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'admin',
                    'user_has_admin': False
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Admin access required")
            
        return view_func(request, *args, **kwargs)
    return wrapper


def analyst_required(view_func):
    """Require user to have is_analyst = True"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:request_magic_link')  # ADDED core:
            
        if not request.user.is_analyst:
            AuditLog.objects.create(
                user=request.user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'analyst', 
                    'user_has_analyst': False
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Analyst access required")
            
        return view_func(request, *args, **kwargs)
    return wrapper


def client_required(view_func):
    """Require user to be a client (not admin or analyst)"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:request_magic_link')  # ADDED core:
            
        if request.user.is_admin or request.user.is_analyst:
            AuditLog.objects.create(
                user=request.user,
                action='unauthorized_access',
                details={
                    'view_name': view_func.__name__,
                    'required_role': 'client',
                    'user_is_admin': request.user.is_admin,
                    'user_is_analyst': request.user.is_analyst
                },
                ip_address=get_client_ip(request)
            )
            return HttpResponseForbidden("Client access only")
            
        return view_func(request, *args, **kwargs)
    return wrapper


def project_access_required(view_func):
    """Ensure user has access to specific project"""
    def wrapper(request, project_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:request_magic_link')  # ADDED core:
            
        try:
            # Convert project_id to UUID if it's a string
            from django.core.exceptions import ValidationError
            try:
                import uuid
                project_id = uuid.UUID(project_id)
            except (ValueError, AttributeError):
                return HttpResponseForbidden("Invalid project ID")
                
            project = Project.objects.get(id=project_id)
            
            # Check access: client owns project OR user is admin/analyst
            has_access = (
                project.client == request.user or 
                request.user.is_admin or 
                request.user.is_analyst
            )
            
            if not has_access:
                AuditLog.objects.create(
                    user=request.user,
                    project=project,
                    action='unauthorized_project_access',
                    details={
                        'project_id': str(project.id),
                        'project_client': str(project.client.id),
                        'attempted_user': str(request.user.id)
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
    """Require user to be assigned analyst for project or admin"""
    def wrapper(request, project_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:request_magic_link')  # ADDED core:
            
        if not request.user.is_analyst and not request.user.is_admin:
            return HttpResponseForbidden("Analyst or admin access required")
            
        try:
            # Convert project_id to UUID if it's a string
            try:
                import uuid
                project_id = uuid.UUID(project_id)
            except (ValueError, AttributeError):
                return HttpResponseForbidden("Invalid project ID")
                
            project = Project.objects.get(id=project_id)
            
            # Check if user is assigned analyst or admin
            has_access = (
                project.assigned_analyst == request.user or 
                request.user.is_admin
            )
            
            if not has_access:
                AuditLog.objects.create(
                    user=request.user,
                    project=project,
                    action='unauthorized_analyst_access',
                    details={
                        'project_id': str(project.id),
                        'assigned_analyst': str(project.assigned_analyst.id) if project.assigned_analyst else None,
                        'attempted_analyst': str(request.user.id)
                    },
                    ip_address=get_client_ip(request)
                )
                return HttpResponseForbidden("Not assigned to this project")
                
        except Project.DoesNotExist:
            return HttpResponseForbidden("Project not found")
            
        request.project = project
        return view_func(request, *args, **kwargs)
    return wrapper