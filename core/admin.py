from django.contrib import admin
from .models import (
    PseudonymousUser, Project, ProjectFile, Deliverable, 
    Message, AuditLog, DownloadToken
)

@admin.register(PseudonymousUser)
class PseudonymousUserAdmin(admin.ModelAdmin):
    list_display = ('alias', 'email', 'is_admin', 'is_analyst', 'created_at')
    list_filter = ('is_admin', 'is_analyst', 'created_at')
    search_fields = ('alias', 'email')
    readonly_fields = ('id', 'created_at', 'last_login')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_id', 'title', 'status', 'client', 'assigned_analyst', 'created_at')
    list_filter = ('status', 'stage', 'support_type', 'created_at')
    search_fields = ('project_id', 'title', 'client__alias')
    readonly_fields = ('id', 'project_id', 'created_at', 'updated_at')
    fieldsets = (
        ('Project Info', {'fields': ('id', 'project_id', 'title', 'description', 'stage', 'support_type')}),
        ('Parties', {'fields': ('client', 'assigned_analyst')}),
        ('Details', {'fields': ('research_area', 'sample_size', 'preferred_methods', 'deadline', 'budget_range')}),
        ('Compliance', {'fields': ('confirms_lawful_use', 'confirms_data_rights', 'irb_approval_provided')}),
        ('Payment', {'fields': ('agreed_price', 'stripe_payment_intent_id', 'payment_status')}),
        ('Status', {'fields': ('status', 'created_at', 'updated_at', 'completed_at')}),
    )

@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'project', 'file_type', 'file_size', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('filename', 'project__project_id')
    readonly_fields = ('id', 'uploaded_at')

@admin.register(Deliverable)
class DeliverableAdmin(admin.ModelAdmin):
    list_display = ('filename', 'project', 'deliverable_type', 'uploaded_at')
    list_filter = ('deliverable_type', 'uploaded_at')
    search_fields = ('filename', 'project__project_id')
    readonly_fields = ('id', 'uploaded_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('project', 'sender', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('project__project_id', 'sender__alias', 'content')
    readonly_fields = ('id', 'created_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'project', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('project__project_id', 'user__alias')
    readonly_fields = ('id', 'created_at')

@admin.register(DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ('deliverable', 'is_one_time', 'created_at', 'expires_at', 'used_at')
    list_filter = ('is_one_time', 'created_at')
    readonly_fields = ('id', 'created_at')
