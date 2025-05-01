/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx}",
    "./src/components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#e6f0fd',
          100: '#cce0fb',
          200: '#99c2f7',
          300: '#66a3f3',
          400: '#3385ef',
          500: '#0066eb',
          600: '#0052bc',
          700: '#003d8d',
          800: '#00295e',
          900: '#00142f',
        },
      },
    },
  },
  plugins: [],
}