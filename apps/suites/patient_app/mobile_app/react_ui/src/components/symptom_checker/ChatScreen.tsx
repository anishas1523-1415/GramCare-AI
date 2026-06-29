import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Camera, Send, ChevronLeft } from 'lucide-react';
import { NeoGlassCard } from '../core/NeoGlassCard';
import { LoadingState } from './LoadingState';
import { TriageResult } from './TriageResult';

interface ChatScreenProps {
  onBack: () => void;
}

export const ChatScreen: React.FC<ChatScreenProps> = ({ onBack }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleSimulateSubmit = () => {
    setIsRecording(false);
    setLoading(true);
    // Simulate AI processing latency
    setTimeout(() => {
      setLoading(false);
      setResult({
        severity: 85,
        condition: "கடுமையான ஒவ்வாமை (Severe Allergic Reaction)",
        homeRemedy: "குளிர்ந்த நீரில் கழுவவும். சொறிய வேண்டாம்.",
        doctorRecommendation: "உடனடியாக டெர்மட்டாலஜிஸ்ட் (Dermatologist) அல்லது அருகில் உள்ள மருத்துவமனைக்கு செல்லவும்.",
        recoveryTime: "3-5 நாட்கள் (Days)"
      });
    }, 4000);
  };

  return (
    <div className="min-h-screen bg-neo-bg flex flex-col p-4 relative">
      
      {/* Header */}
      <motion.div 
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="flex items-center justify-between mb-8 pt-4"
      >
        <button onClick={onBack} className="w-12 h-12 rounded-full neo-button flex items-center justify-center text-gray-600 active:scale-95">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-xl font-bold text-gray-800">சிம்டம் செக்கர் <br/><span className="text-sm font-normal text-gray-500">(Symptom Checker)</span></h1>
        <div className="w-12 h-12 rounded-full neo-in bg-neo-bg" /> {/* Spacer */}
      </motion.div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col justify-center items-center">
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div key="loading" exit={{ opacity: 0, scale: 0.9 }}>
              <LoadingState />
            </motion.div>
          ) : result ? (
            <motion.div key="result" className="w-full flex justify-center">
              <TriageResult {...result} />
            </motion.div>
          ) : (
            <motion.div 
              key="input" 
              className="w-full max-w-sm flex flex-col items-center gap-12"
              exit={{ opacity: 0, y: -50 }}
            >
              {/* Massive Voice Button */}
              <div 
                className={`relative w-48 h-48 rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 ${isRecording ? 'shadow-neo-in' : 'shadow-neo-out'}`}
                onClick={() => setIsRecording(!isRecording)}
              >
                {isRecording && (
                  <motion.div 
                    className="absolute inset-0 rounded-full bg-neo-primary/20"
                    animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}
                <Mic size={64} className={isRecording ? 'text-neo-primary animate-pulse' : 'text-gray-400'} />
              </div>
              <p className="text-center text-gray-500 font-medium text-lg">
                {isRecording ? "பேசவும்... (Listening...)" : "உங்கள் பிரச்சனையை சொல்லுங்கள் (Tap to Speak)"}
              </p>

              {/* Action Buttons */}
              <div className="flex w-full justify-around mt-8">
                <button className="w-16 h-16 rounded-2xl neo-button flex items-center justify-center text-neo-secondary">
                  <Camera size={28} />
                </button>
                {isRecording && (
                  <button 
                    onClick={handleSimulateSubmit}
                    className="w-16 h-16 rounded-2xl bg-neo-primary shadow-[0_8px_16px_rgba(20,184,166,0.4)] flex items-center justify-center text-white"
                  >
                    <Send size={28} />
                  </button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
