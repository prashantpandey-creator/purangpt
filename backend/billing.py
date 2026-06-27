import os
import stripe
import razorpay
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from backend.db_client import get_profile, update_profile, get_db_conn

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
        profile = get_profile(user_id)
        customer_id = profile.get("stripe_customer_id") if profile else None

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

        session = stripe.checkout.Session.create(**session_args)
        
        # Save stripe customer ID back to user profile if available
        if session.customer:
            update_profile(user_id, {"stripe_customer_id": session.customer})

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
    conn = get_db_conn()
    if not conn:
        logger.error("Local Postgres connection not available. Cannot activate subscription.")
        return False

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=period_end_days)

    try:
        with conn.cursor() as cur:
            # 1. Upsert user profile — handles new users who purchase before first chat.
            cur.execute("""
                INSERT INTO profiles (id, role, subscription_status, subscription_plan, subscription_expires_at, created_at, updated_at)
                VALUES (%s, %s, 'active', %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    role = EXCLUDED.role,
                    subscription_status = 'active',
                    subscription_plan = EXCLUDED.subscription_plan,
                    subscription_expires_at = EXCLUDED.subscription_expires_at,
                    updated_at = EXCLUDED.updated_at
            """, (user_id, plan, plan, expires_at, now, now))

            # 2. Insert record in subscriptions table
            cur.execute("""
                INSERT INTO subscriptions (user_id, provider, external_subscription_id, plan, status, current_period_start, current_period_end)
                VALUES (%s, %s, %s, %s, 'active', %s, %s)
            """, (user_id, provider, external_sub_id, plan, now, expires_at))
        conn.commit()

        logger.info(f"Successfully activated '{plan}' plan for user {user_id} via {provider}.")
        return True
    except Exception as e:
        logger.error(f"Error activating subscription for {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def find_user_by_external_sub(external_sub_id: str) -> Optional[str]:
    """Return the user_id that owns a given provider subscription id, or None."""
    if not external_sub_id:
        return None
    conn = get_db_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM subscriptions WHERE external_subscription_id = %s "
                "ORDER BY current_period_start DESC LIMIT 1",
                (external_sub_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"find_user_by_external_sub failed: {e}")
        return None
    finally:
        conn.close()


def downgrade_user(user_id: str) -> bool:
    """Revoke Pro: set the profile back to free + mark the subscription canceled."""
    conn = get_db_conn()
    if not conn:
        return False
    now = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE profiles SET role='free', subscription_status='canceled', "
                "subscription_plan='free', updated_at=%s WHERE id=%s",
                (now, user_id),
            )
            cur.execute(
                "UPDATE subscriptions SET status='canceled' WHERE user_id=%s AND status='active'",
                (user_id,),
            )
        conn.commit()
        logger.info(f"Downgraded user {user_id} to free.")
        return True
    except Exception as e:
        logger.error(f"downgrade_user failed for {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_razorpay_payment(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Verifies Razorpay payment signature.
    """
    if not is_razorpay_configured():
        # Fail CLOSED: if Razorpay isn't configured we cannot verify a real
        # signature, so we must NOT grant access. (Previously this accepted any
        # order id starting with "mock_", letting anyone self-grant Pro when the
        # backend's Razorpay keys were unset.)
        logger.error("verify_razorpay_payment called but Razorpay is not configured — rejecting.")
        return False

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
