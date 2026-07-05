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
  // Tracks the Razorpay modal specifically (separate from `loading`, which
  // only covers the create-order network call). Previously `loading` reset
  // to false the instant rzp.open() returned — since opening the modal is
  // synchronous from JS's perspective — which re-enabled the "Pay" button
  // WHILE the checkout overlay was still on screen, letting a second click
  // create a second order/Payment row for the same booking attempt.
  const [modalOpen, setModalOpen] = useState(false);
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
          setModalOpen(false);
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
            // The charge may still have gone through on Razorpay's side even
            // though this network call failed (dropped connection, backend
            // restart, etc). /webhook is the server-side safety net that
            // marks the payment PAID independently of this call, and
            // /payments/{order_id}/status lets a future retry check before
            // re-charging — surface that instead of implying the money was
            // definitely NOT taken.
            const detail = err.response?.data?.detail;
            onError(
              typeof detail === 'string'
                ? detail
                : 'Could not confirm your payment due to a network error. If you were charged, it will be reconciled automatically — please check your booking status before paying again.'
            );
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
        },
        // Razorpay's own auto-retry-on-failure re-opens the SAME order's
        // checkout, which is harmless (still one order, one Payment row) —
        // but we drive retries explicitly via the "Pay" button instead, so
        // failures always resolve to onError and never leave the modal in
        // a silent internal retry loop the caller doesn't know about.
        retry: { enabled: false },
        // If the patient walks away mid-payment, don't leave the order (and
        // this component) in limbo indefinitely.
        timeout: 300, // seconds
        modal: {
          // Fires when the user closes the checkout without completing or
          // failing a payment (item: "payment cancellation"). Previously
          // nothing happened here at all — no onError call, so the caller's
          // UI never left its "Processing..." affordance and the user had
          // no feedback that nothing was charged.
          ondismiss: function () {
            setModalOpen(false);
            onError("Payment cancelled. You have not been charged.");
          },
        },
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (response: any) {
        setModalOpen(false);
        onError(response.error?.description || "Payment failed. Please try again.");
      });
      setModalOpen(true);
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
        disabled={loading || modalOpen || !isScriptLoaded}
        className="neu-button w-full py-3 bg-teal-500 text-white font-bold rounded-xl disabled:opacity-50"
      >
        {loading ? "Processing..." : modalOpen ? "Waiting for payment…" : `Pay ₹${amount} securely`}
      </button>
    </>
  );
}
