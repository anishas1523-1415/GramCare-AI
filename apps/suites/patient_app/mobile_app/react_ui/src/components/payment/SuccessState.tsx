import React from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

export const SuccessState: React.FC = () => {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-50 bg-neo-bg/90 backdrop-blur-md flex flex-col items-center justify-center"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", damping: 12, stiffness: 200 }}
        className="relative w-40 h-40 flex items-center justify-center"
      >
        {/* Pulsing Success Rings */}
        <motion.div 
          className="absolute inset-0 border-4 border-green-500 rounded-full"
          animate={{ scale: [1, 1.5], opacity: [1, 0] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
        <motion.div 
          className="absolute inset-4 border-4 border-green-400 rounded-full"
          animate={{ scale: [1, 1.3], opacity: [0.8, 0] }}
          transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
        />
        
        {/* Core Checkmark */}
        <div className="w-24 h-24 bg-green-500 rounded-full shadow-[0_0_40px_rgba(34,197,94,0.6)] flex items-center justify-center text-white z-10">
          <motion.div
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Check size={56} strokeWidth={4} />
          </motion.div>
        </div>
      </motion.div>

      <motion.h2 
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-8 text-2xl font-bold text-gray-800"
      >
        வெற்றிகரமானது!
      </motion.h2>
      <motion.p 
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="text-green-600 font-medium text-lg mt-2"
      >
        Payment Successful
      </motion.p>
    </motion.div>
  );
};
