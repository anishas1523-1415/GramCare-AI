import os
import time
import uuid
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import razorpay

router = APIRouter()
logger = logging.getLogger("gramcare.payments")

# ============================================================
# Initialize Razorpay Client
# ============================================================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("Razorpay client initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Razorpay client: {e}")
else:
    logger.warning("Razorpay credentials not found. Payments will operate in MOCK mode.")

# ============================================================
# Schemas
# ============================================================
class OrderCreateRequest(BaseModel):
    patient_id: int
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid.uuid4().hex[:8]}")

class OrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    is_mock: bool = False

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class VerifyPaymentResponse(BaseModel):
    status: str
    message: str

# ============================================================
# Endpoints
# ============================================================
@router.post("/create-order", response_model=OrderResponse)
async def create_order(request: OrderCreateRequest):
    """
    Creates a Razorpay order for a Telehealth Consultation.
    Returns the order_id for the frontend to initiate the payment gateway.
    """
    amount_in_paise = int(request.amount * 100)
    
    if razorpay_client:
        try:
            order_data = {
                "amount": amount_in_paise,
                "currency": request.currency,
                "receipt": request.receipt_id,
                "payment_capture": 1 # Auto capture
            }
            order = razorpay_client.order.create(data=order_data)
            return OrderResponse(
                order_id=order["id"],
                amount=order["amount"],
                currency=order["currency"],
                is_mock=False
            )
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            raise HTTPException(status_code=500, detail="Payment gateway error.")
    else:
        # Mock Mode
        time.sleep(0.5)
        mock_order_id = f"order_{uuid.uuid4().hex[:14]}"
        return OrderResponse(
            order_id=mock_order_id,
            amount=amount_in_paise,
            currency=request.currency,
            is_mock=True
        )

@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(request: VerifyPaymentRequest):
    """
    Verifies the payment signature returned by Razorpay after successful payment.
    """
    if not razorpay_client:
        # If in mock mode, any signature starting with "mock_sig_" is accepted
        if request.razorpay_signature.startswith("mock_sig_"):
            return VerifyPaymentResponse(status="SUCCESS", message="Payment verified successfully (MOCK).")
        else:
            raise HTTPException(status_code=400, detail="Invalid mock signature.")
            
    try:
        params_dict = {
            'razorpay_order_id': request.razorpay_order_id,
            'razorpay_payment_id': request.razorpay_payment_id,
            'razorpay_signature': request.razorpay_signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
        return VerifyPaymentResponse(status="SUCCESS", message="Payment verified successfully.")
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Payment verification failed: Invalid signature.")
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        raise HTTPException(status_code=500, detail="Payment verification error.")

# Legacy endpoint for backward compatibility with frontend during transition
@router.post("/checkout")
async def legacy_checkout(request: dict):
    time.sleep(1)
    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:16]}",
        "status": "SUCCESS",
        "message": f"Successfully processed INR {request.get('amount', 150)} for Telehealth Consultation."
    }
