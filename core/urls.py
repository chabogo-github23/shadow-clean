from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # ... existing paths ...
        # --- Main views ---
    path('', views.home, name='home'), 
    path('login/', views.login_placeholder, name='login'),
    #path('login/', login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
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
