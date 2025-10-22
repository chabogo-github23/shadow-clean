from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # ... existing paths ...
        # --- Main views ---
    path('', views.home, name='home'), 
    path('login/', views.login_placeholder, name='login'),
    path('auth/request-magic-link/', views.request_magic_link, name='request_magic_link'),
    path('auth/verify-magic-link/', views.verify_magic_link, name='verify_magic_link'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('dashboard/client/', views.client_dashboard, name='client_dashboard'),
    path('dashboard/analyst/', views.analyst_dashboard, name='analyst_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('project/submit/', views.submit_project, name='submit_project'),
    path('project/<str:project_id>/', views.project_detail, name='project_detail'),
    path('project/<str:project_id>/payment/', views.payment_page, name='payment_page'),
    path('project/<str:project_id>/payment/create/', views.create_payment, name='create_payment'),
    path('project/<str:project_id>/payment/confirm/', views.confirm_payment, name='confirm_payment'),
    path('project/<str:project_id>/payment/success/', views.payment_success, name='payment_success'),
    path('project/<str:project_id>/payment/cancel/', views.payment_cancel, name='payment_cancel'),
    path('project/<str:project_id>/payment/release/', views.release_payment, name='release_payment'),
    path('project/<str:project_id>/payment/refund/', views.refund_payment, name='refund_payment'),
]
