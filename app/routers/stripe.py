from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.database.database import db
from app.services.logging import logger
from app.models.requests import CreateCheckoutSessionRequest
import stripe
import os

"""
Stripe Router for managing subscription payments.
This router handles Stripe checkout sessions, success/cancel callbacks,
and subscription status checks.
"""

# Hardcoded Stripe API key as requested
stripe.api_key = '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'

router = APIRouter()

# Your domain - update this for production
YOUR_DOMAIN = os.getenv('FRONTEND_URL', 'http://localhost:3000')

@router.post("/create-checkout-session")
def create_checkout_session(request: CreateCheckoutSessionRequest):
    """
    Create a Stripe checkout session for subscription.
    
    Args:
        request (CreateCheckoutSessionRequest): Request containing user_id.
        
    Returns:
        dict: Contains the checkout URL to redirect the user to.
        
    Raises:
        HTTPException: If checkout session creation fails.
    """
    try:
        logger.info(f"Creating checkout session for user: {request.user_id}")
        
        user = db.get_user(request.user_id)
        if not user:
            logger.error(f"User not found: {request.user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"User found: {user['email']}")
        
        # Create Stripe customer if doesn't exist
        if not user.get('stripe_customer_id'):
            logger.info("Creating new Stripe customer")
            customer = stripe.Customer.create(
                email=user['email'],
                name=user['name']
            )
            logger.info(f"Created customer: {customer.id}")
            db.update_user_subscription(
                user_id=request.user_id,
                subscription_status='INACTIVE',
                stripe_customer_id=customer.id
            )
            customer_id = customer.id
        else:
            customer_id = user['stripe_customer_id']
            logger.info(f"Using existing customer: {customer_id}")
        
        # Create checkout session
        logger.info("Creating Stripe checkout session")
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[
                {
                    # Using the price ID from your example
                    'price': 'price_1Rj5CwLnOLAQsDbYmEAAOu7B',
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"http://localhost:8000/stripe/success?session_id={{CHECKOUT_SESSION_ID}}&user_id={request.user_id}",
            cancel_url=f"http://localhost:8000/stripe/cancel?user_id={request.user_id}",
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
async def success(session_id: str, user_id: str):
    """
    Handle successful payment callback from Stripe.
    
    Args:
        session_id (str): The Stripe checkout session ID.
        user_id (str): The user ID.
        
    Returns:
        RedirectResponse: Redirects to dashboard with success message.
    """
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Update user subscription status
            db.update_user_subscription(
                user_id=user_id,
                subscription_status='ACTIVE',
                stripe_subscription_id=session.subscription
            )
            logger.info(f"Subscription activated for user {user_id}")
            
            # Redirect to dashboard
            return RedirectResponse(url=f"{YOUR_DOMAIN}/dashboard?payment=success")
        else:
            return RedirectResponse(url=f"{YOUR_DOMAIN}/dashboard?payment=pending")
            
    except Exception as e:
        logger.error(f"Success callback error: {str(e)}")
        return RedirectResponse(url=f"{YOUR_DOMAIN}/dashboard?payment=error")

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
    return RedirectResponse(url=f"{YOUR_DOMAIN}/payment-required?cancelled=true")

@router.post("/check-subscription")
def check_subscription(request: CreateCheckoutSessionRequest):
    """
    Check if user has an active subscription.
    
    Args:
        request (CreateCheckoutSessionRequest): Request containing user_id.
        
    Returns:
        dict: Contains subscription status information.
    """
    try:
        user = db.get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return {
            "has_active_subscription": user.get('subscription_status') == 'ACTIVE',
            "subscription_status": user.get('subscription_status', 'INACTIVE')
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
        # Test if we can connect to Stripe
        customers = stripe.Customer.list(limit=1)
        
        # Test if the price exists
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