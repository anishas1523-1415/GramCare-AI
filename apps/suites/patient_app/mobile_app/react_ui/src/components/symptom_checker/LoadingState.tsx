import React from 'react';
import { motion } from 'framer-motion';
import { Activity } from 'lucide-react';

export const LoadingState: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center w-full h-full py-12">
      {/* Central Medical Scanner Animation */}
      <div className="relative w-32 h-32 flex items-center justify-center">
        {/* Pulsing Outer Rings */}
        <motion.div 
          className="absolute inset-0 border-4 border-neo-primary rounded-full opacity-20"
          animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div 
          className="absolute inset-2 border-4 border-neo-secondary rounded-full opacity-30"
          animate={{ scale: [1, 1.3, 1], opacity: [0.7, 0, 0.7] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
        />
        
        {/* Core Heartbeat Icon */}
        <motion.div 
          className="bg-white rounded-full p-4 shadow-neo-out text-neo-primary"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        >
          <Activity size={40} />
        </motion.div>

        {/* Scanning Laser Line */}
        <motion.div 
          className="absolute w-full h-1 bg-neo-secondary blur-[2px]"
          initial={{ top: 0 }}
          animate={{ top: "100%" }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <motion.p 
        className="mt-8 text-xl font-bold text-gray-700 tracking-wide text-center"
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        அறிகுறிகளை பகுப்பாய்வு செய்கிறது...
        <br />
        <span className="text-sm font-normal text-gray-500">(Analyzing Symptoms...)</span>
      </motion.p>
    </div>
  );
};
