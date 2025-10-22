from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib import messages
from .models import Project
from .decorators import require_auth, require_admin
from .payment import StripePaymentManager
import json


# ----------------------------
# BASIC / LANDING VIEWS
# ----------------------------

def home(request):
    """Public landing page"""
    return render(request, 'core/landing.html')

def login_placeholder(request):
    """Temporary login page placeholder"""
    return render(request, 'core/login.html')


@require_auth
def dashboard(request):
    """Client dashboard view"""
    projects = Project.objects.filter(client=request.user_obj).order_by('-created_at')
    return render(request, 'core/dashboard.html', {'projects': projects})


@require_admin
def admin_dashboard(request):
    """Admin dashboard"""
    projects = Project.objects.all().order_by('-created_at')
    return render(request, 'core/admin_dashboard.html', {'projects': projects})


# ----------------------------
# PROJECT VIEWS
# ----------------------------

@require_auth
def project_detail(request, project_id):
    """View project details"""
    project = get_object_or_404(Project, project_id=project_id)
    
    # Check authorization
    if project.client.id != request.user_obj.id and not request.user_obj.is_admin:
        return render(request, 'core/access_denied.html', status=403)
    
    return render(request, 'core/project_detail.html', {'project': project})


@require_auth
def submit_project(request):
    """Form to submit a new project"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        file = request.FILES.get('file')

        if not title or not description:
            messages.error(request, 'Title and description are required.')
            return redirect('core:submit_project')

        project = Project.objects.create(
            client=request.user_obj,
            title=title,
            description=description,
            attached_file=file,
            status='pending',
        )
        messages.success(request, 'Project submitted successfully!')
        return redirect('core:project_detail', project_id=project.project_id)
    
    return render(request, 'core/submit_project.html')


# ----------------------------
# PAYMENT VIEWS
# ----------------------------

@require_auth
def create_payment(request, project_id):
    """Create payment intent for project"""
    project = get_object_or_404(Project, project_id=project_id)
    
    if project.client.id != request.user_obj.id:
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
    """Confirm payment after client completes Stripe checkout"""
    project = get_object_or_404(Project, project_id=project_id)
    
    if project.client.id != request.user_obj.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        payment_intent_id = request.POST.get('payment_intent_id', '').strip()
        if not payment_intent_id:
            return JsonResponse({'error': 'Missing payment intent ID'}, status=400)
        
        success = StripePaymentManager.confirm_payment(project, payment_intent_id)
        
        if success:
            return JsonResponse({'success': True, 'message': 'Payment confirmed'})
        else:
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
        else:
            return JsonResponse({'error': 'Refund failed'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_auth
def payment_page(request, project_id):
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user_obj.id:
        return render(request, 'core/access_denied.html', status=403)
    
    return render(request, 'core/payment.html', {
        'project': project,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    })


@require_auth
def payment_success(request, project_id):
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user_obj.id:
        return render(request, 'core/access_denied.html', status=403)
    return render(request, 'core/payment_success.html', {'project': project})


@require_auth
def payment_cancel(request, project_id):
    project = get_object_or_404(Project, project_id=project_id)
    if project.client.id != request.user_obj.id:
        return render(request, 'core/access_denied.html', status=403)
    return render(request, 'core/payment_cancel.html', {'project': project})
