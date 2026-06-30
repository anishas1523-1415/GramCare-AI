export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'neo-bg': '#F8FAFC',
        'neo-primary': '#3B82F6',
      },
      boxShadow: {
        'neo-out': '8px 8px 16px #E2E8F0, -8px -8px 16px #ffffff',
        'neo-in': 'inset 8px 8px 16px #E2E8F0, inset -8px -8px 16px #ffffff',
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.05)',
      },
      backgroundImage: {
        'glass-gradient': 'linear-gradient(135deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.4))',
      },
      animation: {
        'scan': 'scan 2s ease-in-out infinite',
      },
      keyframes: {
        scan: {
          '0%, 100%': { top: '0%' },
          '50%': { top: '100%' },
        }
      }
    },
  },
  plugins: [],
}
