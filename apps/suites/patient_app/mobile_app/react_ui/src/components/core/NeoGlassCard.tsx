import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { twMerge } from 'tailwind-merge';

interface NeoGlassCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  variant?: 'glass' | 'neo-out' | 'neo-in';
}

export const NeoGlassCard: React.FC<NeoGlassCardProps> = ({ 
  children, 
  className, 
  variant = 'glass',
  ...props 
}) => {
  const baseClasses = "rounded-3xl p-6 overflow-hidden relative";
  
  const variantClasses = {
    'glass': 'neo-glass',
    'neo-out': 'bg-neo-bg shadow-neo-out',
    'neo-in': 'bg-neo-bg shadow-neo-in'
  };

  return (
    <motion.div 
      className={twMerge(baseClasses, variantClasses[variant], className)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
      {...props}
    >
      {/* Decorative Gradient Orb for Glass effect */}
      {variant === 'glass' && (
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-neo-primary/20 rounded-full blur-3xl pointer-events-none" />
      )}
      {children}
    </motion.div>
  );
};
