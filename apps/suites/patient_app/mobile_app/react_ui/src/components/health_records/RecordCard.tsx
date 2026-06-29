import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Volume2, Pill, TestTube2, Syringe } from 'lucide-react';
import { NeoGlassCard } from '../core/NeoGlassCard';

export type RecordType = 'prescription' | 'lab' | 'vaccine';

interface RecordCardProps {
  id: string;
  type: RecordType;
  title: string;
  date: string;
  doctorName: string;
}

export const RecordCard: React.FC<RecordCardProps> = ({ type, title, date, doctorName }) => {
  const [isPlaying, setIsPlaying] = useState(false);

  const getTheme = () => {
    switch (type) {
      case 'prescription':
        return { color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30', Icon: Pill };
      case 'lab':
        return { color: 'text-green-500', bg: 'bg-green-500/10', border: 'border-green-500/30', Icon: TestTube2 };
      case 'vaccine':
        return { color: 'text-purple-500', bg: 'bg-purple-500/10', border: 'border-purple-500/30', Icon: Syringe };
    }
  };

  const theme = getTheme();
  const Icon = theme.Icon;

  const handlePlayVoice = () => {
    setIsPlaying(true);
    setTimeout(() => setIsPlaying(false), 3000); // Mock audio duration
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      whileTap={{ scale: 0.98 }}
    >
      <NeoGlassCard variant="glass" className={`border-2 ${theme.border} ${theme.bg} flex items-center justify-between p-4 mb-4`}>
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-2xl bg-white shadow-neo-out ${theme.color}`}>
            <Icon size={24} />
          </div>
          <div>
            <h3 className="font-bold text-gray-800 text-lg">{title}</h3>
            <p className="text-sm text-gray-600 font-medium">{doctorName}</p>
            <p className="text-xs text-gray-400 mt-1">{date}</p>
          </div>
        </div>

        {/* Voice Playback Button */}
        <button 
          onClick={handlePlayVoice}
          className={`p-4 rounded-full transition-all duration-300 ${isPlaying ? 'bg-neo-bg shadow-neo-in text-neo-primary animate-pulse' : 'bg-neo-bg shadow-neo-out text-gray-400 active:shadow-neo-in'}`}
        >
          <Volume2 size={24} />
        </button>
      </NeoGlassCard>
    </motion.div>
  );
};
