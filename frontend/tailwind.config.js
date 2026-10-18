/** @type {import('tailwindcss').Config} */
// Colours are CSS variables (src/index.css) so dark mode follows the system
// setting without a dark: variant on every class.
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: v('navy'),
        paper: v('paper'),
        card: v('card'),
        ink: v('ink'),
        rule: v('rule'),
        subtle: v('subtle'),
        zebra: v('zebra'),
        'on-navy': v('on-navy'),
        'on-flag': v('on-flag'),
        'flag-hallucinated': v('hallucinated'),
        'flag-uncertain': v('uncertain'),
        'flag-verified': v('verified'),
      },
      fontFamily: {
        serif: ['Lora', 'Source Serif 4', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        deva: ['"Noto Sans Devanagari"', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(11,37,69,0.04)',
        lift: '0 2px 4px rgba(0,0,0,0.06), 0 8px 24px rgba(11,37,69,0.10)',
      },
      maxWidth: {
        page: '1100px',
      },
    },
  },
  plugins: [],
}
