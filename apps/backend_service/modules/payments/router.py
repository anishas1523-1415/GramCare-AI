import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter()

class PaymentRequest(BaseModel):
    patient_id: str
    amount: float
    currency: str = "INR"
    card_token: str

class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    message: str

@router.post("/checkout", response_model=PaymentResponse)
async def process_payment(request: PaymentRequest):
    """
    Mock Production-Grade Payment Gateway (Stripe/Razorpay placeholder).
    Validates the token, processes payment, and issues a transaction ID.
    """
    # Simulate network latency to third-party payment provider
    time.sleep(1.5)
    
    if not request.card_token or request.card_token == "invalid_token":
        raise HTTPException(status_code=400, detail="Payment declined: Invalid card details.")
        
    transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
    
    return PaymentResponse(
        transaction_id=transaction_id,
        status="SUCCESS",
        message=f"Successfully processed {request.currency} {request.amount} for Telehealth Consultation."
    )
