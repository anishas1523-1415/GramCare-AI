"use client";

import React, { useState } from 'react';
import Script from 'next/script';
import api from '../lib/api';

interface RazorpayCheckoutProps {
  amount: number; // in INR
  patientId: number;
  onSuccess: (paymentId: string) => void;
  onError: (error: string) => void;
}

export default function RazorpayCheckout({ amount, patientId, onSuccess, onError }: RazorpayCheckoutProps) {
  const [loading, setLoading] = useState(false);
  const [isScriptLoaded, setIsScriptLoaded] = useState(false);

  const handlePayment = async () => {
    if (!isScriptLoaded) {
      onError("Payment gateway is still loading. Please try again in a moment.");
      return;
    }

    setLoading(true);

    try {
      // 1. Create Order on Backend
      const { data: order } = await api.post('/payments/create-order', {
        amount,
        patient_id: patientId,
      });

      if (order.is_mock) {
        // Handle mock payment directly without opening Razorpay modal
        const { data: verifyData } = await api.post('/payments/verify', {
          razorpay_order_id: order.order_id,
          razorpay_payment_id: "mock_pay_" + Math.random().toString(36).substring(7),
          razorpay_signature: "mock_sig_valid"
        });
        
        if (verifyData.status === "SUCCESS") {
          onSuccess("mock_payment_id");
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
              onSuccess(response.razorpay_payment_id);
            } else {
              onError("Payment verification failed.");
            }
          } catch (err: any) {
            onError(err.response?.data?.detail || "Payment verification failed.");
          }
        },
        prefill: {
          name: "Patient Name", // Typically fetched from AuthContext
          email: "patient@example.com",
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
