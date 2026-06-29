import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Volume2 } from 'lucide-react';
import { NeoGlassCard } from '../core/NeoGlassCard';

interface AuthScreenProps {
  onLogin?: () => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ onLogin }) => {
  const [selectedUser, setSelectedUser] = useState<number | null>(null);

  // Mock Family Members for Rural Access
  const familyMembers = [
    { id: 1, name: "தாத்தா", role: "Grandfather", img: "https://api.dicebear.com/7.x/avataaars/svg?seed=Grandpa" },
    { id: 2, name: "அம்மா", role: "Mother", img: "https://api.dicebear.com/7.x/avataaars/svg?seed=Mother" },
    { id: 3, name: "நான்கு", role: "Self", img: "https://api.dicebear.com/7.x/avataaars/svg?seed=Self" }
  ];

  const handleSelect = (id: number) => {
    // Play voice confirmation in production
    setSelectedUser(id);
    
    // Add latency mask transition here
    setTimeout(() => {
      if (onLogin) onLogin();
    }, 800);
  };

  return (
    <div className="min-h-screen bg-neo-bg flex flex-col items-center justify-center p-6 relative overflow-hidden">
      
      {/* Voice Prompt Assistant Bubble */}
      <motion.div 
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="absolute top-12 flex flex-col items-center gap-3"
      >
        <div className="w-16 h-16 rounded-full neo-button flex items-center justify-center text-neo-primary cursor-pointer hover:scale-105 active:scale-95 transition-transform">
          <Volume2 size={32} />
        </div>
        <p className="text-gray-600 font-medium text-lg tracking-wide text-center">யார் பயன்படுத்துகிறீர்கள்?<br/><span className="text-sm font-normal text-gray-500">(Tap your photo)</span></p>
      </motion.div>

      {/* Family Profiles */}
      <div className="w-full max-w-sm mt-24 space-y-6">
        <AnimatePresence>
          {familyMembers.map((member, i) => (
            <motion.div
              key={member.id}
              initial={{ x: -100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: i * 0.15 + 0.3, type: "spring" }}
            >
              <NeoGlassCard 
                variant="neo-out"
                className={`cursor-pointer transition-all duration-300 ${selectedUser === member.id ? 'ring-4 ring-neo-primary scale-105' : 'hover:scale-105 active:scale-95'}`}
                onClick={() => handleSelect(member.id)}
              >
                <div className="flex items-center gap-6">
                  <div className="w-20 h-20 rounded-2xl bg-white shadow-inner overflow-hidden border-2 border-white/50">
                    <img src={member.img} alt={member.name} className="w-full h-full object-cover" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-800">{member.name}</h2>
                    <p className="text-gray-500">{member.role}</p>
                  </div>
                </div>
              </NeoGlassCard>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Bottom Voice Input (Alternative) */}
      <motion.div 
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 1 }}
        className="absolute bottom-12 w-full px-8"
      >
        <NeoGlassCard variant="glass" className="p-4 flex items-center justify-center gap-4 text-white">
          <div className="p-4 rounded-full bg-neo-primary/20 text-neo-primary animate-pulse">
            <Mic size={24} />
          </div>
          <p className="text-gray-700 font-medium">பேசி உள்நுழைய (Voice Login)</p>
        </NeoGlassCard>
      </motion.div>

    </div>
  );
};
