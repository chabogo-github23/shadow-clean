"""
Stripe payment and escrow management for ShadowIQ
Handles payment processing, holds, and payouts
"""

import stripe
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Project, AuditLog

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripePaymentManager:
    """Manage Stripe payments and escrow"""
    
    @staticmethod
    def create_payment_intent(project, amount_cents):
        """Create a Stripe PaymentIntent for project payment"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                metadata={
                    'project_id': project.project_id,
                    'project_uuid': str(project.id),
                    'client_alias': project.client.alias,
                },
                description=f"ShadowIQ Project {project.project_id}: {project.title}",
            )
            
            # Update project with payment intent ID
            project.stripe_payment_intent_id = intent.id
            project.payment_status = 'processing'
            project.save()
            
            return intent
        except stripe.error.StripeError as e:
            print(f"Stripe error creating payment intent: {e}")
            return None
    
    @staticmethod
    def confirm_payment(project, payment_intent_id):
        """Confirm payment and hold funds in escrow"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                # Payment successful - hold funds
                project.payment_status = 'completed'
                project.status = 'accepted'
                project.save()
                
                # Log audit trail
                AuditLog.objects.create(
                    project=project,
                    action='payment_processed',
                    details={
                        'amount': intent.amount,
                        'currency': intent.currency,
                        'payment_intent_id': payment_intent_id,
                    }
                )
                
                return True
            else:
                project.payment_status = 'failed'
                project.save()
                return False
        except stripe.error.StripeError as e:
            print(f"Stripe error confirming payment: {e}")
            project.payment_status = 'failed'
            project.save()
            return False
    
    @staticmethod
    def release_payment_to_analyst(project, analyst_stripe_account_id):
        """Release escrowed funds to analyst after project completion"""
        try:
            if not project.stripe_payment_intent_id:
                return False
            
            intent = stripe.PaymentIntent.retrieve(project.stripe_payment_intent_id)
            
            if intent.status != 'succeeded':
                return False
            
            # Calculate platform fee (e.g., 20%)
            platform_fee_percent = 0.20
            total_amount = intent.amount
            platform_fee = int(total_amount * platform_fee_percent)
            analyst_payout = total_amount - platform_fee
            
            # Create transfer to analyst's Stripe account
            transfer = stripe.Transfer.create(
                amount=analyst_payout,
                currency='usd',
                destination=analyst_stripe_account_id,
                metadata={
                    'project_id': project.project_id,
                    'analyst_alias': project.assigned_analyst.alias if project.assigned_analyst else 'Unknown',
                },
                description=f"ShadowIQ Project {project.project_id} Payout",
            )
            
            # Log audit trail
            AuditLog.objects.create(
                project=project,
                action='payout_released',
                details={
                    'transfer_id': transfer.id,
                    'amount': analyst_payout,
                    'platform_fee': platform_fee,
                }
            )
            
            return True
        except stripe.error.StripeError as e:
            print(f"Stripe error releasing payment: {e}")
            return False
    
    @staticmethod
    def refund_payment(project, reason=''):
        """Refund payment to client"""
        try:
            if not project.stripe_payment_intent_id:
                return False
            
            intent = stripe.PaymentIntent.retrieve(project.stripe_payment_intent_id)
            
            if intent.status != 'succeeded':
                return False
            
            # Create refund
            refund = stripe.Refund.create(
                payment_intent=project.stripe_payment_intent_id,
                metadata={
                    'project_id': project.project_id,
                    'reason': reason,
                }
            )
            
            project.payment_status = 'refunded'
            project.save()
            
            # Log audit trail
            AuditLog.objects.create(
                project=project,
                action='payment_refunded',
                details={
                    'refund_id': refund.id,
                    'amount': refund.amount,
                    'reason': reason,
                }
            )
            
            return True
        except stripe.error.StripeError as e:
            print(f"Stripe error refunding payment: {e}")
            return False
    
    @staticmethod
    def get_payment_status(payment_intent_id):
        """Get current payment status"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return intent.status
        except stripe.error.StripeError as e:
            print(f"Stripe error getting payment status: {e}")
            return None
    
    @staticmethod
    def create_invoice(project, description, amount_cents):
        """Create a Stripe invoice for project"""
        try:
            invoice = stripe.Invoice.create(
                customer=project.client.alias,  # Use alias as customer ID
                amount=amount_cents,
                currency='usd',
                description=description,
                metadata={
                    'project_id': project.project_id,
                    'project_uuid': str(project.id),
                },
            )
            
            return invoice
        except stripe.error.StripeError as e:
            print(f"Stripe error creating invoice: {e}")
            return None
