/** @type {import('tailwindcss').Config} */
// All colours are tokens; components never use literal hex values.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    borderRadius: {
      none: '0',
      DEFAULT: '3px',
      full: '9999px',
    },
    extend: {
      colors: {
        navy: '#0B2545',
        paper: '#FBFAF8',
        card: '#FFFFFF',
        ink: '#1A1A1A',
        muted: '#5A6472',
        rule: '#E2E0DB',
        'flag-no': '#B23A48',
        'flag-no-bg': '#FBEEF0',
        'flag-unc': '#8A6212', // text and chips (AA on white)
        'flag-unc-accent': '#C08A2E', // underlines and bars ONLY (2.8:1, fails AA as text)
        'flag-unc-bg': '#FBF3E3',
        'flag-yes': '#2E6B4F',
        'flag-yes-bg': '#EAF3EE',
      },
      fontFamily: {
        // Lora / Inter have no Devanagari: the Noto fallbacks keep Hindi in matching styles.
        serif: ['Lora', '"Noto Serif Devanagari"', 'Georgia', 'serif'],
        sans: ['Inter', '"Noto Sans Devanagari"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        overlay: '0 2px 6px rgba(11,37,69,0.08), 0 12px 32px rgba(11,37,69,0.14)',
      },
    },
  },
  plugins: [],
}
