from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
import uuid
import secrets
import string

def generate_project_id():
    """Generate unique project ID in format SIQ-XXXXXX"""
    from django.conf import settings
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{settings.PROJECT_ID_PREFIX}-{random_part}"

class PseudonymousUser(models.Model):
    """User with pseudonymous authentication (no traditional login)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alias = models.CharField(max_length=255, unique=True)
    email = models.EmailField(null=True, blank=True)  # Optional
    magic_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    magic_token_expires = models.DateTimeField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    is_analyst = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.alias

class Project(models.Model):
    """Research project submission"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('in_progress', 'In Progress'),
        ('qa', 'QA Review'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('disputed', 'Disputed'),
    ]
    
    STAGE_CHOICES = [
        ('proposal', 'Proposal'),
        ('data_analysis', 'Data Analysis'),
        ('literature_review', 'Literature Review'),
        ('methodology', 'Methodology'),
        ('full_project', 'Full Project'),
    ]
    
    SUPPORT_TYPES = [
        ('sample_size', 'Sample Size Calculation'),
        ('analysis_plan', 'Analysis Plan'),
        ('statistical_analysis', 'Statistical Analysis'),
        ('data_cleaning', 'Data Cleaning'),
        ('methodology_review', 'Methodology Review'),
        ('report_writing', 'Report Writing'),
        ('reproducible_notebook', 'Reproducible Notebook'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_id = models.CharField(max_length=20, unique=True, default=generate_project_id)
    client = models.ForeignKey(PseudonymousUser, on_delete=models.PROTECT, related_name='projects')
    assigned_analyst = models.ForeignKey(PseudonymousUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_projects')
    
    title = models.CharField(max_length=500)
    description = models.TextField()
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    support_type = models.CharField(max_length=50, choices=SUPPORT_TYPES)
    research_area = models.CharField(max_length=255)
    
    sample_size = models.IntegerField(null=True, blank=True)
    preferred_methods = models.TextField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    budget_range = models.CharField(max_length=100, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    
    # Compliance & Ethics
    confirms_lawful_use = models.BooleanField(default=False)
    confirms_data_rights = models.BooleanField(default=False)
    irb_approval_provided = models.BooleanField(default=False)
    
    # Pricing & Payment
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ], default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project_id']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.project_id} - {self.title}"

class ProjectFile(models.Model):
    """Files uploaded for a project"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='project_files/%Y/%m/%d/')
    filename = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(PseudonymousUser, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.project.project_id} - {self.filename}"

class Deliverable(models.Model):
    """Project deliverables"""
    DELIVERABLE_TYPES = [
        ('report', 'PDF Report'),
        ('notebook', 'Reproducible Notebook'),
        ('code', 'Code Bundle'),
        ('data_log', 'Data Processing Log'),
        ('sow', 'Statement of Work'),
        ('qa_report', 'QA Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='deliverables')
    deliverable_type = models.CharField(max_length=50, choices=DELIVERABLE_TYPES)
    file = models.FileField(upload_to='deliverables/%Y/%m/%d/')
    filename = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(PseudonymousUser, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.project.project_id} - {self.get_deliverable_type_display()}"

class Message(models.Model):
    """Chat messages between client and admin"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(PseudonymousUser, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.project.project_id} - {self.sender.alias}"

class AuditLog(models.Model):
    """Immutable audit trail for compliance"""
    ACTION_CHOICES = [
        ('project_submitted', 'Project Submitted'),
        ('project_accepted', 'Project Accepted'),
        ('status_changed', 'Status Changed'),
        ('file_uploaded', 'File Uploaded'),
        ('file_downloaded', 'File Downloaded'),
        ('deliverable_uploaded', 'Deliverable Uploaded'),
        ('payment_processed', 'Payment Processed'),
        ('message_sent', 'Message Sent'),
        ('project_rejected', 'Project Rejected'),
        ('dispute_filed', 'Dispute Filed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(PseudonymousUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'action']),
            models.Index(fields=['user', 'action']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.created_at}"

class DownloadToken(models.Model):
    """One-time download tokens for deliverables"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deliverable = models.ForeignKey(Deliverable, on_delete=models.CASCADE, related_name='download_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_one_time = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Token for {self.deliverable.filename}"
