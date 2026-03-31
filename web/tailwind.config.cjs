/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "Noto Sans TC",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      colors: {
        // Inverted scale: ink-950 = white (body bg), ink-100 = near-black (body text)
        ink: {
          50: "#000000",
          100: "#111111",
          200: "#222222",
          300: "#444444",
          400: "#666666",
          500: "#888888",
          600: "#aaaaaa",
          700: "#cccccc",
          800: "#e5e5e5",
          900: "#f5f5f5",
          950: "#ffffff",
        },
        accent: {
          DEFAULT: "#000000",
          dim: "#333333",
          glow: "#444444",
        },
      },
      backgroundImage: {
        mesh: "none",
      },
      boxShadow: {
        glass: "none",
        card: "2px 2px 0px rgba(0,0,0,1)",
        glow: "none",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
        smooth: "cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        snappy: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-down": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.2s ease-out forwards",
        "fade-in": "fade-in 0.15s ease-out forwards",
        "scale-in": "scale-in 0.2s ease-out forwards",
        "slide-down": "slide-down 0.15s ease-out forwards",
        shimmer: "shimmer 1.8s linear infinite",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
