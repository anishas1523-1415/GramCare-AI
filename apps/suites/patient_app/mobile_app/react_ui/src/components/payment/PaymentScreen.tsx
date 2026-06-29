import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { QrCode, Banknote, Smartphone, Receipt } from 'lucide-react';
import { NeoGlassCard } from '../core/NeoGlassCard';
import { SuccessState } from './SuccessState';

export const PaymentScreen: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handlePayment = () => {
    setIsProcessing(true);
    // Simulate API Call / UPI Deep Link Delay
    setTimeout(() => {
      setIsProcessing(false);
      setIsSuccess(true);
      
      // Auto dismiss success screen after 3 seconds
      setTimeout(() => {
        setIsSuccess(false);
      }, 3000);
    }, 1500);
  };

  return (
    <div className="flex flex-col h-full p-4 relative pb-24">
      <AnimatePresence>
        {isSuccess && <SuccessState />}
      </AnimatePresence>

      {/* Header */}
      <motion.div 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="mb-8 pt-4"
      >
        <h1 className="text-2xl font-bold text-gray-800">கட்டணம் <br/><span className="text-sm font-normal text-gray-500">(Payments)</span></h1>
      </motion.div>

      {/* Outstanding Bill Card */}
      <NeoGlassCard variant="glass" className="border-2 border-neo-primary/30 bg-neo-primary/5 flex flex-col items-center justify-center p-8 mb-8">
        <Receipt size={40} className="text-neo-primary mb-2 opacity-50" />
        <p className="text-gray-500 font-medium">பணம் செலுத்த வேண்டியவை (Due)</p>
        <h2 className="text-5xl font-bold text-gray-800 mt-2">₹150</h2>
        <p className="text-sm text-gray-400 mt-4">Dr. Ram Consultation (Oct 12)</p>
      </NeoGlassCard>

      {/* Payment Options */}
      <div className="grid grid-cols-1 gap-6 w-full max-w-sm mx-auto">
        
        {/* UPI Option */}
        <motion.div whileTap={{ scale: 0.95 }}>
          <NeoGlassCard 
            variant="neo-out" 
            className="flex items-center gap-6 cursor-pointer hover:shadow-neo-in transition-shadow"
            onClick={handlePayment}
          >
            <div className="p-4 bg-white rounded-2xl shadow-neo-out text-neo-secondary">
              <Smartphone size={32} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-800">UPI மூலம் (GPay)</h3>
              <p className="text-sm text-gray-500">Pay using UPI app</p>
            </div>
          </NeoGlassCard>
        </motion.div>

        {/* QR Code Option */}
        <motion.div whileTap={{ scale: 0.95 }}>
          <NeoGlassCard 
            variant="neo-out" 
            className="flex items-center gap-6 cursor-pointer hover:shadow-neo-in transition-shadow"
            onClick={handlePayment}
          >
            <div className="p-4 bg-white rounded-2xl shadow-neo-out text-neo-primary">
              <QrCode size={32} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-800">QR குறியீடு ஸ்கேன்</h3>
              <p className="text-sm text-gray-500">Scan QR Code</p>
            </div>
          </NeoGlassCard>
        </motion.div>

        {/* Cash Option */}
        <motion.div whileTap={{ scale: 0.95 }}>
          <NeoGlassCard 
            variant="neo-out" 
            className="flex items-center gap-6 cursor-pointer hover:shadow-neo-in transition-shadow"
            onClick={handlePayment}
          >
            <div className="p-4 bg-white rounded-2xl shadow-neo-out text-green-500">
              <Banknote size={32} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-800">பணம் (Cash)</h3>
              <p className="text-sm text-gray-500">Pay at the Clinic</p>
            </div>
          </NeoGlassCard>
        </motion.div>

      </div>
    </div>
  );
};
