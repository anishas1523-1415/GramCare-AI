import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Camera, Search } from 'lucide-react';
import { RecordCard, RecordType } from './RecordCard';
import { NeoGlassCard } from '../core/NeoGlassCard';

export const EHRDashboard: React.FC = () => {
  const [isScanning, setIsScanning] = useState(false);

  // Mock data representing offline SQLite sync
  const mockRecords = [
    { id: '1', type: 'prescription' as RecordType, title: 'காய்ச்சல் மருந்து (Fever Meds)', date: 'Oct 12, 2026', doctorName: 'Dr. Ram (GH)' },
    { id: '2', type: 'lab' as RecordType, title: 'இரத்த பரிசோதனை (Blood Test)', date: 'Oct 10, 2026', doctorName: 'Apollo Labs' },
    { id: '3', type: 'vaccine' as RecordType, title: 'கோவிட் தடுப்பூசி (Covid Vax)', date: 'Jan 05, 2025', doctorName: 'Govt Camp' },
  ];

  const handleSmartUpload = () => {
    setIsScanning(true);
    setTimeout(() => setIsScanning(false), 3000);
  };

  return (
    <div className="flex flex-col h-full p-4 relative pb-24">
      {/* Header */}
      <motion.div 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="mb-6 pt-4"
      >
        <h1 className="text-2xl font-bold text-gray-800">சுகாதார பதிவேடுகள் <br/><span className="text-sm font-normal text-gray-500">(Health Wallet)</span></h1>
      </motion.div>

      {/* Search & Filter */}
      <NeoGlassCard variant="neo-in" className="flex items-center gap-3 p-3 mb-6">
        <Search className="text-gray-400" size={20} />
        <input 
          type="text" 
          placeholder="தேடல் (Search records...)" 
          className="bg-transparent outline-none w-full text-gray-700 placeholder-gray-400"
        />
      </NeoGlassCard>

      {/* Records List */}
      <div className="flex-1 overflow-y-auto hide-scrollbar space-y-2">
        {mockRecords.map((record, index) => (
          <RecordCard key={record.id} {...record} />
        ))}
      </div>

      {/* Smart Upload FAB */}
      <motion.button 
        whileTap={{ scale: 0.9 }}
        onClick={handleSmartUpload}
        className="absolute bottom-28 right-6 w-16 h-16 rounded-full bg-neo-primary shadow-[0_8px_24px_rgba(20,184,166,0.5)] flex items-center justify-center text-white z-10"
      >
        {isScanning ? (
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-8 h-8 border-4 border-white/30 border-t-white rounded-full"
          />
        ) : (
          <Camera size={28} />
        )}
      </motion.button>

      {/* Scanning Overlay Effect */}
      {isScanning && (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-neo-primary/10 backdrop-blur-sm z-0 flex items-center justify-center pointer-events-none"
        >
          <div className="w-full h-1 bg-neo-primary shadow-[0_0_20px_rgba(20,184,166,1)] animate-scan" />
        </motion.div>
      )}
    </div>
  );
};
