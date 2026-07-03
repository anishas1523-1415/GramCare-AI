"use client";

import React, { useState } from 'react';
import Script from 'next/script';
import api from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

interface RazorpayCheckoutProps {
  amount: number; // in INR
  /** Called with the ORDER id after successful verification — the booking
   * API requires this order id as proof of payment (server-enforced). */
  onSuccess: (orderId: string) => void;
  onError: (error: string) => void;
}

export default function RazorpayCheckout({ amount, onSuccess, onError }: RazorpayCheckoutProps) {
  const [loading, setLoading] = useState(false);
  const [isScriptLoaded, setIsScriptLoaded] = useState(false);
  const { user } = useAuth();

  const handlePayment = async () => {
    if (!isScriptLoaded) {
      onError("Payment gateway is still loading. Please try again in a moment.");
      return;
    }

    setLoading(true);

    try {
      // 1. Create Order on Backend (always for the authenticated caller —
      // the old client-supplied patient_id field was an impersonation hole)
      const { data: order } = await api.post('/payments/create-order', { amount });

      if (order.is_mock) {
        // Handle mock payment directly without opening Razorpay modal.
        // The mock signature must now be derived from the order id (backend
        // no longer accepts a bare "mock_sig_valid" for any order — see
        // apps/backend_service/modules/payments/router.py verify_payment).
        const { data: verifyData } = await api.post('/payments/verify', {
          razorpay_order_id: order.order_id,
          razorpay_payment_id: "mock_pay_" + Math.random().toString(36).substring(7),
          razorpay_signature: `mock_sig_${order.order_id}_valid`
        });
        
        if (verifyData.status === "SUCCESS") {
          onSuccess(order.order_id);
        } else {
          onError("Mock verification failed");
        }
        setLoading(false);
        return;
      }

      // 2. Open Razorpay Checkout Modal for real payment
      const options = {
        key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID, 
        amount: order.amount,
        currency: order.currency,
        name: "GramCare AI",
        description: "Telehealth Consultation",
        order_id: order.order_id,
        handler: async function (response: any) {
          try {
            // 3. Verify Payment Signature on Backend
            const { data: verifyData } = await api.post('/payments/verify', {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });

            if (verifyData.status === "SUCCESS") {
              onSuccess(response.razorpay_order_id);
            } else {
              onError("Payment verification failed.");
            }
          } catch (err: any) {
            onError(err.response?.data?.detail || "Payment verification failed.");
          }
        },
        // Previously hardcoded placeholder values ("Patient Name",
        // patient@example.com) regardless of who was actually paying — real
        // payment records/receipts would show fake customer info. Now
        // sourced from the authenticated user; contact number still falls
        // back to a placeholder since phone number isn't currently part of
        // the User model (schemas.UserCreate has no phone field either) —
        // tracked as a follow-up.
        prefill: {
          name: user?.full_name || user?.username || "Patient",
          email: user?.email || "",
          contact: "9999999999"
        },
        theme: {
          color: "#14b8a6" // teal-500
        }
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (response: any) {
        onError(response.error.description);
      });
      rzp.open();

    } catch (err: any) {
      onError(err.response?.data?.detail || "Failed to initiate payment.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Script 
        src="https://checkout.razorpay.com/v1/checkout.js" 
        onLoad={() => setIsScriptLoaded(true)}
      />
      <button 
        onClick={handlePayment} 
        disabled={loading || !isScriptLoaded}
        className="neu-button w-full py-3 bg-teal-500 text-white font-bold rounded-xl disabled:opacity-50"
      >
        {loading ? "Processing..." : `Pay ₹${amount} securely`}
      </button>
    </>
  );
}
