import os
import stripe
import razorpay
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from backend.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Load API Keys and configuration from environment
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "price_mock_pro")
STRIPE_SCHOLAR_PRICE_ID = os.getenv("STRIPE_SCHOLAR_PRICE_ID", "price_mock_scholar")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_PRO_PLAN_ID = os.getenv("RAZORPAY_PRO_PLAN_ID", "plan_mock_pro")
RAZORPAY_SCHOLAR_PLAN_ID = os.getenv("RAZORPAY_SCHOLAR_PLAN_ID", "plan_mock_scholar")

# Initialize clients if keys are present
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def is_stripe_configured() -> bool:
    return bool(STRIPE_API_KEY and not STRIPE_API_KEY.startswith("your_"))

def is_razorpay_configured() -> bool:
    return bool(RAZORPAY_KEY_ID and not RAZORPAY_KEY_ID.startswith("your_") and RAZORPAY_KEY_SECRET)

def create_stripe_checkout(user_id: str, plan: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
    """
    Creates a Stripe Checkout Session for the selected plan.
    If Stripe is not configured in the environment, it returns a mock session for testing.
    """
    if plan not in ["pro", "scholar"]:
        raise ValueError("Invalid plan name. Must be 'pro' or 'scholar'.")

    price_id = STRIPE_PRO_PRICE_ID if plan == "pro" else STRIPE_SCHOLAR_PRICE_ID

    if not is_stripe_configured():
        logger.warning("Stripe is not configured. Returning a mock Checkout Session URL.")
        # Return a simulated success URL that the frontend can redirect to
        # Add a custom mock token so the frontend can verify the simulation
        mock_success_url = f"{success_url}?session_id=mock_stripe_checkout_{user_id}_{plan}"
        return {
            "url": mock_success_url,
            "id": f"mock_cs_{user_id}_{plan}",
            "mock": True
        }

    try:
        # Create or retrieve customer ID
        supabase = get_supabase()
        customer_id = None
        if supabase:
            profile = supabase.table("profiles").select("stripe_customer_id").eq("id", user_id).execute()
            if profile.data and profile.data[0].get("stripe_customer_id"):
                customer_id = profile.data[0]["stripe_customer_id"]

        session_args = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1,
            }],
            "mode": "subscription",
            "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": cancel_url,
            "client_reference_id": user_id,
            "metadata": {
                "user_id": user_id,
                "plan": plan
            }
        }
        if customer_id:
            session_args["customer"] = customer_id
        else:
            # Let Stripe create a new customer and retrieve email
            if supabase:
                auth_user = supabase.table("profiles").select("display_name").eq("id", user_id).execute()
                # If we had the email, we'd pass it. Stripe handles customer creation automatically.

        session = stripe.checkout.Session.create(**session_args)
        
        # Save stripe customer ID back to user profile if available
        if supabase and session.customer:
            supabase.table("profiles").update({"stripe_customer_id": session.customer}).eq("id", user_id).execute()

        return {
            "url": session.url,
            "id": session.id,
            "mock": False
        }
    except Exception as e:
        logger.error(f"Error creating Stripe Checkout Session: {e}")
        raise

def create_razorpay_order(user_id: str, plan: str) -> Dict[str, Any]:
    """
    Creates a Razorpay Subscription or Order for the selected plan.
    If Razorpay is not configured, it returns a mock order for testing.
    """
    if plan not in ["pro", "scholar"]:
        raise ValueError("Invalid plan. Must be 'pro' or 'scholar'.")

    # Prices in INR (paise)
    plan_amounts = {
        "pro": 49900,      # ₹499 per month
        "scholar": 99900   # ₹999 per month
    }
    amount = plan_amounts[plan]

    if not is_razorpay_configured():
        logger.warning("Razorpay is not configured. Returning a mock Order.")
        return {
            "id": f"mock_rzp_order_{user_id}_{plan}",
            "amount": amount,
            "currency": "INR",
            "mock": True,
            "notes": {
                "user_id": user_id,
                "plan": plan
            }
        }

    try:
        # Create standard order (simplest for testing/starting, can upgrade to recurring Subscriptions)
        order_data = {
            "amount": amount,
            "currency": "INR",
            "receipt": f"receipt_{user_id}_{int(datetime.now(timezone.utc).timestamp())}",
            "notes": {
                "user_id": user_id,
                "plan": plan
            }
        }
        order = razorpay_client.order.create(data=order_data)
        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "mock": False,
            "notes": order.get("notes", {})
        }
    except Exception as e:
        logger.error(f"Error creating Razorpay Order: {e}")
        raise

def activate_user_subscription(user_id: str, plan: str, provider: str, external_sub_id: str, period_end_days: int = 30):
    """
    Upgrades user profile to the specified subscription tier.
    Logs subscription details in the subscriptions database table.
    """
    supabase = get_supabase()
    if not supabase:
        logger.error("Supabase client is not available. Cannot activate subscription.")
        return False

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=period_end_days)

    try:
        # 1. Update user profile
        supabase.table("profiles").update({
            "role": plan,
            "subscription_status": "active",
            "subscription_plan": plan,
            "subscription_expires_at": expires_at.isoformat(),
            "updated_at": now.isoformat()
        }).eq("id", user_id).execute()

        # 2. Insert record in subscriptions table
        supabase.table("subscriptions").insert({
            "user_id": user_id,
            "provider": provider,
            "external_subscription_id": external_sub_id,
            "plan": plan,
            "status": "active",
            "current_period_start": now.isoformat(),
            "current_period_end": expires_at.isoformat()
        }).execute()

        logger.info(f"Successfully activated '{plan}' plan for user {user_id} via {provider}.")
        return True
    except Exception as e:
        logger.error(f"Error activating subscription for {user_id}: {e}")
        return False

def verify_razorpay_payment(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Verifies Razorpay payment signature.
    """
    if not is_razorpay_configured():
        # Allow validation for mock payments
        return razorpay_order_id.startswith("mock_")

    try:
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
        return True
    except Exception as e:
        logger.error(f"Razorpay payment verification failed: {e}")
        return False
