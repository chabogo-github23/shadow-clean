from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import login, logout
import secrets
import uuid
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from .models import PseudonymousUser, Project, AuditLog, AuthToken
from .payment import StripePaymentManager
from .decorators import (
    pseudonymous_user_required as require_auth,
    admin_required as require_admin,
    analyst_required as require_analyst,
    client_required,
    get_client_ip,
)


# ----------------------------
# BASIC / LANDING VIEWS
# ----------------------------

def home(request):
    """Public landing page"""
    return render(request, 'core/landing.html')


def login_placeholder(request):
    """Temporary login page placeholder"""
    return render(request, 'core/login.html')


@client_required
def client_dashboard(request):
    """Client dashboard - shows user's projects"""
    projects = Project.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'core/client_dashboard.html', {
        'projects': projects,
        'user': request.user
    })


@require_analyst
def analyst_dashboard(request):
    """Analyst dashboard - shows assigned projects"""
    projects = Project.objects.filter(assigned_analyst=request.user).order_by('-created_at')
    return render(request, 'core/analyst_dashboard.html', {
        'projects': projects,
        'user': request.user
    })


@require_admin
def admin_dashboard(request):
    """Admin dashboard - shows all users and projects"""
    users = PseudonymousUser.objects.all().order_by('-created_at')
    projects = Project.objects.all().order_by('-created_at')
    return render(request, 'core/admin_dashboard.html', {
        'users': users,
        'projects': projects,
        'user': request.user
    })


# ----------------------------
# MAGIC LINK AUTH
# ----------------------------

def request_magic_link(request):
    """Generate and display magic link on screen instead of emailing it."""
    if request.method == 'POST':
        alias = request.POST.get('alias')
        email = request.POST.get('email')

        if not alias and not email:
            return render(request, 'auth/request_magic_link.html', {
                'error': 'Please provide either an alias or email.'
            })

        # Find or create pseudonymous user
        user, created = PseudonymousUser.objects.get_or_create(
            alias=alias or f"User-{get_random_string(6)}",
            defaults={'email': email or None}
        )

        # Generate magic token
        token = secrets.token_urlsafe(32)
        user.magic_token = token
        user.magic_token_expires = timezone.now() + timezone.timedelta(hours=24)
        user.save()

        # Build verification link
        magic_link = request.build_absolute_uri(
            f'/auth/verify-magic-link/?token={token}'
        )

        # Log request
        AuditLog.objects.create(
            user=user,
            action='magic_link_requested',
            details={'alias': user.alias},
            ip_address=get_client_ip(request)
        )

        # ✅ Show the link directly on-screen (no email)
        return render(request, 'auth/magic_link_display.html', {
            'magic_link': magic_link,
            'user': user,
        })
    return render(request, 'auth/request_magic_link.html')


def verify_magic_link(request):
    """Verify magic token and log user in"""
    token = request.GET.get('token')
    
    if not token:
        return render(request, 'core/invalid_token.html', {  # This one is in core/
            'error': 'No token provided'
        })
    
    try:
        # Find user with valid, non-expired token
        user = PseudonymousUser.objects.get(
            magic_token=token,
            magic_token_expires__gt=timezone.now()
        )
        
        # ✅ Instead of Django's login()
        request.session['pseudonymous_user_id'] = str(user.id)
        
        # Update user record
        user.last_login = timezone.now()
        user.magic_token = None  # Invalidate token after use
        user.magic_token_expires = None
        user.save()
        
        # Log successful login
        AuditLog.objects.create(
            user=user,
            action='user_logged_in',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        # Redirect to appropriate dashboard
        if user.is_admin:
            return redirect('core:admin_dashboard')
        elif user.is_analyst:
            return redirect('core:analyst_dashboard')
        else:
            return redirect('core:client_dashboard')
            
    except PseudonymousUser.DoesNotExist:
        return render(request, 'core/invalid_token.html', {  # This one is in core/
            'error': 'Invalid or expired token'
        })
    except Exception as e:
        return render(request, 'core/invalid_token.html', {  # This one is in core/
            'error': f'Authentication error: {str(e)}'
        })


def logout_view(request):
    """End pseudonymous session"""
    user_id = request.session.pop('pseudonymous_user_id', None)
    if user_id:
        try:
            user = PseudonymousUser.objects.get(id=user_id)
            AuditLog.objects.create(
                user=user,
                action='user_logged_out',
                ip_address=get_client_ip(request)
            )
        except PseudonymousUser.DoesNotExist:
            pass
    return redirect('home')


# ----------------------------
# PROJECT VIEWS
# ----------------------------

@require_auth
def project_detail(request, project_id):
    """View project details"""
    project = get_object_or_404(Project, project_id=project_id)

    if project.client.id != request.user.id and not request.user.is_admin:
        return render(request, 'core/access_denied.html', status=403)

    return render(request, 'core/project_detail.html', {'project': project})


@client_required
def submit_project(request):
    """Project submission view - protected by client_required"""
    if request.method == 'POST':
        project = Project.objects.create(
            client=request.user,
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            stage=request.POST.get('stage'),
            support_type=request.POST.get('support_type'),
            research_area=request.POST.get('research_area'),
            confirms_lawful_use=bool(request.POST.get('lawful_use')),
            confirms_data_rights=bool(request.POST.get('data_rights'))
        )
        AuditLog.objects.create(
            user=request.user,
            project=project,
            action='project_submitted'
        )
        return redirect('core:project_detail', project_id=project.project_id)

    return render(request, 'core/submit_project.html')


# ----------------------------
# PAYMENT VIEWS
# ----------------------------

@require_auth
def create_payment(request, project_id):
    """Create payment intent for project"""
    project = get_object_or_404(Project, project_id=project_id)

    if project.client.id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            if amount <= 0:
                return JsonResponse({'error': 'Invalid amount'}, status=400)

            amount_cents = int(amount * 100)
            intent = StripePaymentManager.create_payment_intent(project, amount_cents)

            if not intent:
                return JsonResponse({'error': 'Failed to create payment'}, status=500)

            return JsonResponse({
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': amount,
            })
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid amount'}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_auth
def confirm_payment(request, project_id):
    """Confirm payment after checkout"""
    project = get_object_or_404(Project, project_id=project_id)

    if project.client.id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        payment_intent_id = request.POST.get('payment_intent_id', '').strip()
        if not payment_intent_id:
            return JsonResponse({'error': 'Missing payment intent ID'}, status=400)

        success = StripePaymentManager.confirm_payment(project, payment_intent_id)

        if success:
            return JsonResponse({'success': True, 'message': 'Payment confirmed'})
        return JsonResponse({'error': 'Payment confirmation failed'}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_admin
def release_payment(request, project_id):
    """Release escrowed payment to analyst"""
    project = get_object_or_404(Project, project_id=project_id)

    if request.method == 'POST':
        if project.status != 'completed':
            return JsonResponse({'error': 'Project must be completed first'}, status=400)

        analyst_stripe_account = request.POST.get('analyst_stripe_account', '')
        if not analyst_stripe_account:
            return JsonResponse({'error': 'Analyst Stripe account not configured'}, status=400)

        success = StripePaymentManager.release_payment_to_analyst(project, analyst_stripe_account)
        return JsonResponse({'success': success})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_admin
def refund_payment(request, project_id):
    """Refund payment to client"""
    project = get_object_or_404(Project, project_id=project_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        success = StripePaymentManager.refund_payment(project, reason)

        if success:
            project.status = 'rejected'
            project.save()
            return JsonResponse({'success': True})
        return JsonResponse({'error': 'Refund failed'}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_auth
def payment_page(request, project_id):
    """Display Stripe payment page"""
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user.id:
        return render(request, 'core/access_denied.html', status=403)

    return render(request, 'core/payment.html', {
        'project': project,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    })


@require_auth
def payment_success(request, project_id):
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user.id:
        return render(request, 'core/access_denied.html', status=403)
    return render(request, 'core/payment_success.html', {'project': project})


@require_auth
def payment_cancel(request, project_id):
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user.id:
        return render(request, 'core/access_denied.html', status=403)
    return render(request, 'core/payment_cancel.html', {'project': project})
