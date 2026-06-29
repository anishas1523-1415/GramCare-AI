import React from 'react';
import { motion } from 'framer-motion';
import { NeoGlassCard } from '../core/NeoGlassCard';
import { AlertTriangle, Home, Stethoscope, Clock } from 'lucide-react';

interface TriageResultProps {
  severity: number;
  condition: string;
  homeRemedy: string;
  doctorRecommendation: string;
  recoveryTime: string;
}

export const TriageResult: React.FC<TriageResultProps> = ({
  severity,
  condition,
  homeRemedy,
  doctorRecommendation,
  recoveryTime
}) => {
  const isCritical = severity > 70;
  
  return (
    <motion.div 
      initial={{ y: 50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="w-full max-w-lg space-y-6"
    >
      {/* Main Severity Card */}
      <NeoGlassCard variant="glass" className={`border-2 ${isCritical ? 'border-red-500/50 bg-red-500/10' : 'border-green-500/50 bg-green-500/10'}`}>
        <div className="flex items-center gap-4">
          <div className={`p-4 rounded-full ${isCritical ? 'bg-red-500/20 text-red-500 animate-pulse' : 'bg-green-500/20 text-green-500'}`}>
            <AlertTriangle size={32} />
          </div>
          <div>
            <h2 className={`text-2xl font-bold ${isCritical ? 'text-red-600' : 'text-green-600'}`}>
              தீவிரத்தன்மை: {severity}%
            </h2>
            <p className="text-gray-700 font-medium">{condition}</p>
          </div>
        </div>
      </NeoGlassCard>

      {/* Actionable Advice Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <NeoGlassCard variant="neo-out" className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-neo-secondary">
            <Home size={20} />
            <h3 className="font-bold">கை வைத்தியம் (Home Remedy)</h3>
          </div>
          <p className="text-sm text-gray-600">{homeRemedy}</p>
        </NeoGlassCard>

        <NeoGlassCard variant="neo-out" className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-neo-primary">
            <Stethoscope size={20} />
            <h3 className="font-bold">மருத்துவர் (Doctor)</h3>
          </div>
          <p className="text-sm text-gray-600">{doctorRecommendation}</p>
        </NeoGlassCard>
      </div>

      {/* Recovery Timeline */}
      <NeoGlassCard variant="neo-in" className="flex items-center gap-4">
        <div className="p-3 bg-white rounded-full shadow-neo-out text-gray-500">
          <Clock size={24} />
        </div>
        <div>
          <h3 className="font-bold text-gray-700">குணமடைய ஆகும் நேரம்</h3>
          <p className="text-sm text-gray-500">{recoveryTime}</p>
        </div>
      </NeoGlassCard>

    </motion.div>
  );
};
