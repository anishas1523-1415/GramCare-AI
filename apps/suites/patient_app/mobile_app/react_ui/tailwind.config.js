/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        neo: {
          bg: '#e0e5ec',
          light: '#ffffff',
          dark: '#a3b1c6',
          primary: '#14b8a6', // Teal 500
          secondary: '#6366f1', // Indigo 500
        }
      },
      boxShadow: {
        'neo-out': '9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5)',
        'neo-in': 'inset 6px 6px 10px 0 rgba(163,177,198, 0.7), inset -6px -6px 10px 0 rgba(255,255,255, 0.8)',
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
      },
      backgroundImage: {
        'glass-gradient': 'linear-gradient(135deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0.1) 100%)',
      }
    },
  },
  plugins: [],
}
