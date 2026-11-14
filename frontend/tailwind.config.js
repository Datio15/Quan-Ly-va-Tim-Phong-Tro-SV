/** @type {import('tailwindcss').Config} */
// Màu thương hiệu EasyRent lấy từ logo: xanh teal (chữ "Easy"), cam (chữ "Rent", ngôi nhà), xanh lá (mũi tên).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef7f7", 100: "#d5ebec", 200: "#acd6d8", 300: "#7bbcc0", 400: "#4c9aa0",
          500: "#2a7c84", 600: "#1d6770", 700: "#185a62", 800: "#13444b", 900: "#0e3237",
        },
        accent: {
          50: "#fff4ec", 100: "#ffe3cf", 200: "#fdc59f", 300: "#f9a46c", 400: "#f58c47",
          500: "#f07a30", 600: "#dc6420", 700: "#b44f19",
        },
        leaf: { 100: "#e6f4dc", 500: "#78b858", 600: "#5e9d42" },
      },
      fontFamily: {
        sans: ["Montserrat", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
