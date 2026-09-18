/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0B2545',
        paper: '#FBFAF8',
        ink: '#1A1A1A',
        rule: '#E2E0DB',
        'flag-hallucinated': '#B23A48',
        'flag-uncertain': '#C08A2E',
        'flag-verified': '#2E6B4F',
      },
      fontFamily: {
        serif: ['Lora', 'Source Serif 4', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        deva: ['"Noto Sans Devanagari"', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
