import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Video, PhoneOff, MicOff, Camera, ArrowLeft } from 'lucide-react';
import './index.css';

export default function App() {
  const [inCall, setInCall] = useState(false);

  return (
    <div className="w-full h-screen bg-[#f0f4f8] overflow-hidden flex flex-col font-sans">
      <AnimatePresence mode="wait">
        {!inCall ? (
          <motion.div key="alerts" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, x: -100 }} className="flex-1 flex flex-col">
            {/* Header */}
            <header className="pt-12 pb-6 px-6 bg-white/60 backdrop-blur-xl border-b border-white/50 shadow-sm z-10">
              <h1 className="text-2xl font-bold text-blue-900">Dr. Sarah Jenkins</h1>
              <p className="text-blue-600 font-medium">Critical Alerts Feed</p>
            </header>

            {/* Alerts List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <AlertCard 
                patient="Ramesh K." 
                age="45" 
                symptom="Severe Chest Pain" 
                severity="92%" 
                time="2 mins ago" 
                onCall={() => setInCall(true)}
              />
              <AlertCard 
                patient="Lakshmi S." 
                age="60" 
                symptom="High Fever (103F)" 
                severity="75%" 
                time="15 mins ago" 
                warning
              />
            </div>
          </motion.div>
        ) : (
          <motion.div key="call" initial={{ opacity: 0, y: 100 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 100 }} className="flex-1 flex flex-col bg-gray-900 relative">
            
            {/* Main Patient Video (Mock) */}
            <div className="absolute inset-0 bg-gray-800 flex items-center justify-center">
              <div className="text-gray-600 flex flex-col items-center">
                <Video size={64} className="mb-4 opacity-50" />
                <p>Patient Video Feed (Connecting...)</p>
              </div>
            </div>

            {/* Top Bar */}
            <div className="absolute top-0 w-full pt-12 pb-4 px-6 bg-gradient-to-b from-black/60 to-transparent flex justify-between items-center z-10">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                <span className="text-white font-bold tracking-wider">00:14</span>
              </div>
              <div className="bg-blue-500/20 backdrop-blur-md px-3 py-1 rounded-full border border-blue-500/50">
                <span className="text-blue-400 text-xs font-bold">Low Bandwidth Mode</span>
              </div>
            </div>

            {/* Doctor PIP */}
            <div className="absolute top-24 right-4 w-28 h-40 bg-black rounded-2xl border-2 border-white/20 overflow-hidden shadow-2xl z-10">
              <div className="w-full h-full bg-gray-700 flex items-center justify-center">
                <span className="text-gray-400 text-xs">You</span>
              </div>
            </div>

            {/* Controls */}
            <div className="absolute bottom-10 w-full px-8 flex justify-between items-center z-10">
              <button className="w-14 h-14 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-white border border-white/20 active:bg-white/20">
                <Camera size={24} />
              </button>
              <button 
                onClick={() => setInCall(false)}
                className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center text-white shadow-[0_0_20px_rgba(239,68,68,0.5)] hover:bg-red-600 transition-colors"
              >
                <PhoneOff size={28} />
              </button>
              <button className="w-14 h-14 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-white border border-white/20 active:bg-white/20">
                <MicOff size={24} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AlertCard({ patient, age, symptom, severity, time, warning, onCall }: any) {
  return (
    <div className={`p-5 rounded-3xl backdrop-blur-xl border relative overflow-hidden shadow-lg ${warning ? 'bg-orange-500/10 border-orange-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
      {!warning && <div className="absolute inset-0 bg-red-500/5 animate-pulse pointer-events-none" />}
      
      <div className="flex justify-between items-start relative z-10">
        <div className="flex gap-4">
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-md ${warning ? 'bg-orange-500' : 'bg-red-500 animate-bounce'}`}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-lg">{patient}, {age}</h3>
            <p className="text-gray-600 font-medium">{symptom}</p>
            <p className="text-sm text-gray-500 mt-1">{time}</p>
          </div>
        </div>
        <div className="text-right">
          <span className={`text-2xl font-black tracking-tighter ${warning ? 'text-orange-600' : 'text-red-600'}`}>
            {severity}
          </span>
        </div>
      </div>

      {!warning && onCall && (
        <button 
          onClick={onCall}
          className="mt-4 w-full py-3 bg-red-500 text-white font-bold rounded-xl shadow-[0_4px_16px_rgba(239,68,68,0.4)] flex items-center justify-center gap-2 active:scale-95 transition-transform"
        >
          <Video size={20} />
          Initiate Telehealth
        </button>
      )}
    </div>
  );
}
