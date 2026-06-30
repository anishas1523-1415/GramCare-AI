"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Calendar, Clock, User, CheckCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import RazorpayCheckout from '../../components/RazorpayCheckout';
import api from '../../lib/api';

export default function AppointmentBooking() {
  const { user } = useAuth();
  const [step, setStep] = useState(1);
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [bookingConfirmed, setBookingConfirmed] = useState(false);
  const [error, setError] = useState('');
  
  // Hardcoded for demo, normally fetched via API
  const DOCTOR_ID = 2; // Dr. Sarah Jenkins
  const CONSULTATION_FEE = 150; 

  const handlePaymentSuccess = async (paymentId: string) => {
    try {
      // 1. Create the appointment in DB
      const scheduledDateTime = new Date(`${selectedDate}T${selectedTime}:00`).toISOString();
      
      await api.post('/appointments/book', {
        doctor_id: DOCTOR_ID,
        scheduled_at: scheduledDateTime,
        triage_summary: symptoms
      });
      
      setBookingConfirmed(true);
      setStep(3);
    } catch (err: any) {
      setError("Payment succeeded, but failed to book appointment. Please contact support.");
    }
  };

  const handlePaymentError = (errMsg: string) => {
    setError(errMsg);
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to book an appointment.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24 flex items-center justify-center">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-2xl w-full p-8 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-teal-400/5 z-0"></div>
        <div className="z-10 relative">
          
          <h1 className="text-3xl font-bold mb-8 text-center text-[var(--foreground)]">Book Consultation</h1>
          
          {/* Progress Steps */}
          <div className="flex justify-between mb-8 relative">
            <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-200 dark:bg-gray-800 -z-10 -translate-y-1/2"></div>
            {[1, 2, 3].map((num) => (
              <div 
                key={num} 
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold border-4 border-[var(--background)] ${step >= num ? 'bg-teal-500 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-800'}`}
              >
                {num}
              </div>
            ))}
          </div>

          {step === 1 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><Calendar className="text-indigo-500" /> Select Date & Time</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold mb-2">Preferred Date</label>
                  <input 
                    type="date" 
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-teal-400 focus:outline-none" 
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-semibold mb-2">Preferred Time</label>
                  <input 
                    type="time" 
                    value={selectedTime}
                    onChange={(e) => setSelectedTime(e.target.value)}
                    className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-teal-400 focus:outline-none" 
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-semibold mb-2">Brief Symptoms (Optional)</label>
                  <textarea 
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                    placeholder="E.g., Mild fever and sore throat..."
                    className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none"
                    rows={3}
                  />
                </div>
              </div>

              <div className="mt-8 flex justify-end">
                <button 
                  onClick={() => setStep(2)}
                  disabled={!selectedDate || !selectedTime}
                  className="neu-button px-8 py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50"
                >
                  Continue to Payment
                </button>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><User className="text-teal-500" /> Confirm & Pay</h2>
              
              <div className="bg-white/40 dark:bg-black/40 p-6 rounded-xl border border-white/20 mb-8 space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-500">Doctor:</span>
                  <span className="font-bold">Dr. Sarah Jenkins</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Date:</span>
                  <span className="font-bold">{selectedDate}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Time:</span>
                  <span className="font-bold">{selectedTime}</span>
                </div>
                <hr className="border-gray-300 dark:border-gray-700" />
                <div className="flex justify-between text-lg">
                  <span className="font-bold">Consultation Fee:</span>
                  <span className="font-bold text-teal-500">₹{CONSULTATION_FEE}</span>
                </div>
              </div>

              {error && <p className="text-red-500 mb-4 text-center text-sm font-semibold">{error}</p>}

              <div className="flex gap-4">
                <button 
                  onClick={() => setStep(1)}
                  className="neu-button px-6 py-3 bg-gray-200 dark:bg-gray-800 font-bold rounded-xl w-1/3 text-gray-700 dark:text-gray-200"
                >
                  Back
                </button>
                <div className="w-2/3">
                  <RazorpayCheckout 
                    amount={CONSULTATION_FEE}
                    patientId={1} // Temporary hardcode, normally extracted from token
                    onSuccess={handlePaymentSuccess}
                    onError={handlePaymentError}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {step === 3 && bookingConfirmed && (
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center py-10">
              <div className="w-24 h-24 bg-green-500/20 text-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle size={48} />
              </div>
              <h2 className="text-3xl font-bold mb-4">Booking Confirmed!</h2>
              <p className="text-gray-500 mb-8">
                Your consultation with Dr. Sarah Jenkins is scheduled for {selectedDate} at {selectedTime}.
              </p>
              <button 
                onClick={() => window.location.href = '/'}
                className="neu-button px-8 py-3 bg-teal-500 text-white font-bold rounded-xl"
              >
                Return to Dashboard
              </button>
            </motion.div>
          )}

        </div>
      </motion.div>
    </div>
  );
}
