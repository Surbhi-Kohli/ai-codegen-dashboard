/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#e6f1ff",
          500: "#0a84ff",
          600: "#0070e0",
        },
      },
    },
  },
  plugins: [],
};
