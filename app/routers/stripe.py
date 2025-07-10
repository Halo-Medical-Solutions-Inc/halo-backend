from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.database.database import db
from app.services.logging import logger
from app.models.requests import CreateCheckoutSessionRequest, CheckSubscriptionRequest, StartFreeTrialRequest
import stripe
import os
from app.config import settings

"""
Stripe Router for managing subscription payments.
This router handles Stripe checkout sessions, success/cancel callbacks,
and subscription status checks.
"""

stripe.api_key = settings.STRIPE_API_KEY
router = APIRouter()

@router.post("/create-checkout-session")
def create_checkout_session(request: CreateCheckoutSessionRequest):
    """
    Create a Stripe checkout session for subscription.
    
    Args:
        request (CreateCheckoutSessionRequest): Request containing user_id and plan_type.
        
    Returns:
        dict: Contains the checkout URL to redirect the user to.
        
    Raises:
        HTTPException: If checkout session creation fails.
    """
    try:
        logger.info(f"Creating checkout session for user: {request.user_id}, plan: {request.plan_type}")
        
        user = db.get_user(request.user_id)
        if not user:
            logger.error(f"User not found: {request.user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"User found: {user['email']}")
        
        if request.plan_type == 'monthly':
            price_id = 'price_1Rj5CwLnOLAQsDbYmEAAOu7B'
            plan_name = 'MONTHLY'
        elif request.plan_type == 'yearly':
            price_id = 'price_1Rj6GXLnOLAQsDbY1BMrVimb'
            plan_name = 'YEARLY'
        else:
            raise HTTPException(status_code=400, detail="Invalid plan type. Must be 'monthly' or 'yearly'")
        
        logger.info(f"Using price ID: {price_id} for plan: {plan_name}")
        
        if not user.get('subscription', {}).get('stripe_customer_id'):
            logger.info("Creating new Stripe customer")
            customer = stripe.Customer.create(
                email=user['email'],
                name=user['name']
            )
            logger.info(f"Created customer: {customer.id}")
            db.update_user_subscription(
                user_id=request.user_id,
                plan='NO_PLAN',
                stripe_customer_id=customer.id
            )
            customer_id = customer.id
        else:
            customer_id = user['subscription']['stripe_customer_id']
            logger.info(f"Using existing customer: {customer_id}")
        
        logger.info("Creating Stripe checkout session")
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{settings.BACKEND_URL}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}&user_id={request.user_id}&plan={plan_name}",
            cancel_url=f"{settings.BACKEND_URL}/stripe/cancel?user_id={request.user_id}",
        )
        
        logger.info(f"Created checkout session: {checkout_session.id}")
        return {"checkout_url": checkout_session.url}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        logger.error(f"Stripe error type: {type(e)}")
        logger.error(f"Stripe error code: {getattr(e, 'code', 'No code')}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        logger.error(f"Create checkout session error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")

@router.get("/success")
async def success(session_id: str, user_id: str, plan: str):
    """
    Handle successful payment callback from Stripe.
    
    Args:
        session_id (str): The Stripe checkout session ID.
        user_id (str): The user ID.
        plan (str): The subscription plan (MONTHLY or YEARLY).
        
    Returns:
        RedirectResponse: Redirects to dashboard with success message.
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            db.update_user_subscription(
                user_id=user_id,
                plan=plan,
                stripe_subscription_id=session.subscription
            )
            logger.info(f"Subscription activated for user {user_id} with plan {plan}")
            
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?payment=success")
        else:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?payment=pending")
            
    except Exception as e:
        logger.error(f"Success callback error: {str(e)}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?payment=error")

@router.get("/cancel")
async def cancel(user_id: str):
    """
    Handle cancelled payment callback from Stripe.
    
    Args:
        user_id (str): The user ID.
        
    Returns:
        RedirectResponse: Redirects to payment required page.
    """
    logger.info(f"Payment cancelled for user {user_id}")
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/payment-required?cancelled=true")

@router.post("/start-free-trial")
def start_free_trial(request: StartFreeTrialRequest):
    """
    Start free trial for a user.
    
    Args:
        request (StartFreeTrialRequest): Request containing user_id.
        
    Returns:
        dict: Updated user information.
        
    Raises:
        HTTPException: If user not found or trial already used.
    """
    try:
        user = db.get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.get('subscription', {}).get('free_trial_used'):
            raise HTTPException(status_code=400, detail="Free trial already used")
        
        updated_user = db.start_free_trial(request.user_id)
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to start free trial")
        
        return {"message": "Free trial started successfully", "user": updated_user}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start free trial error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start free trial")

@router.post("/check-subscription")
def check_subscription(request: CheckSubscriptionRequest):
    """
    Check if user has an active subscription or valid free trial.
    
    Args:
        request (CheckSubscriptionRequest): Request containing user_id.
        
    Returns:
        dict: Contains subscription status information.
    """
    try:
        user = db.get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        subscription = user.get('subscription', {})
        plan = subscription.get('plan', 'NO_PLAN')
        has_active_subscription = plan in ['MONTHLY', 'YEARLY', 'FREE', 'CUSTOM']
        
        if plan == 'FREE':
            trial_expired = db.check_trial_expired(request.user_id)
            if trial_expired:
                db.update_user_subscription(request.user_id, 'NO_PLAN')
                has_active_subscription = False
                plan = 'NO_PLAN'
            else:
                has_active_subscription = True
        
        return {
            "has_active_subscription": has_active_subscription,
            "subscription": {
                "plan": plan,
                "free_trial_used": subscription.get('free_trial_used', False),
                "free_trial_expiration_date": subscription.get('free_trial_expiration_date')
            }
        }
        
    except Exception as e:
        logger.error(f"Check subscription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check subscription")

@router.get("/test")
def test_stripe():
    """
    Test Stripe connection and price ID.
    """
    try:
        customers = stripe.Customer.list(limit=1)

        price = stripe.Price.retrieve('price_1Rj5CwLnOLAQsDbYmEAAOu7B')
        
        return {
            "stripe_connected": True,
            "price_id": price.id,
            "price_amount": price.unit_amount,
            "price_currency": price.currency
        }
    except Exception as e:
        logger.error(f"Stripe test error: {str(e)}")
        return {
            "stripe_connected": False,
            "error": str(e)
        } 