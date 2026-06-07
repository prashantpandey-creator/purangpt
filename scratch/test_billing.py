import os
import sys
import uuid
import dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
dotenv.load_dotenv()

from backend.billing import (
    create_stripe_checkout,
    create_razorpay_order,
    activate_user_subscription,
    is_stripe_configured,
    is_razorpay_configured
)

def run_tests():
    print("--- Billing Integration Test ---")
    print(f"Stripe Configured: {is_stripe_configured()}")
    print(f"Razorpay Configured: {is_razorpay_configured()}")
    
    # Generate a dummy user ID
    dummy_user_id = str(uuid.uuid4())
    print(f"Using dummy User ID: {dummy_user_id}")
    
    print("\n1. Testing Stripe Checkout Session (Mock/Real):")
    try:
        stripe_res = create_stripe_checkout(
            user_id=dummy_user_id,
            plan="pro",
            success_url="http://localhost:8000/billing.html",
            cancel_url="http://localhost:8000/pricing.html"
        )
        print("Stripe Response Success:")
        print(f"  ID: {stripe_res.get('id')}")
        print(f"  URL: {stripe_res.get('url')}")
        print(f"  Is Mock: {stripe_res.get('mock')}")
    except Exception as e:
        print(f"Stripe Test Failed: {e}")
        
    print("\n2. Testing Razorpay Order Creation (Mock/Real):")
    try:
        rzp_res = create_razorpay_order(
            user_id=dummy_user_id,
            plan="scholar"
        )
        print("Razorpay Response Success:")
        print(f"  ID: {rzp_res.get('id')}")
        print(f"  Amount: {rzp_res.get('amount')}")
        print(f"  Is Mock: {rzp_res.get('mock')}")
    except Exception as e:
        print(f"Razorpay Test Failed: {e}")

if __name__ == "__main__":
    run_tests()
