/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#12181f",
        panelmuted: "#1a2129",
        accent: "#22c55e",
      },
    },
  },
  plugins: [],
};
