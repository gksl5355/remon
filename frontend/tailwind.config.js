/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",             // 다크모드 class 기반
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/scrollbar'),
  ],
};
