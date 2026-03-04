import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			heading: ['"Bricolage Grotesque"', 'sans-serif'],
  			body: ['Lexend', 'sans-serif'],
  			mono: ['"JetBrains Mono"', 'monospace'],
  		},
  		colors: {
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		keyframes: {
  			'glow-word': {
  				'0%, 100%': { opacity: '0.3' },
  				'50%': { opacity: '1' },
  			},
  			'fade-in': {
  				from: { opacity: '0' },
  				to: { opacity: '1' },
  			},
  			'fade-out': {
  				from: { opacity: '1' },
  				to: { opacity: '0' },
  			},
  			'slide-up': {
  				from: { opacity: '0', transform: 'translateY(8px)' },
  				to: { opacity: '1', transform: 'translateY(0)' },
  			},
  			'slide-down': {
  				from: { opacity: '0', transform: 'translateY(-8px)' },
  				to: { opacity: '1', transform: 'translateY(0)' },
  			},
  			'scale-in': {
  				from: { opacity: '0', transform: 'scale(0.95)' },
  				to: { opacity: '1', transform: 'scale(1)' },
  			},
  			'scale-out': {
  				from: { opacity: '1', transform: 'scale(1)' },
  				to: { opacity: '0', transform: 'scale(0.95)' },
  			},
  			'spring-in': {
  				'0%': { opacity: '0', transform: 'scale(0.9)' },
  				'70%': { transform: 'scale(1.02)' },
  				'100%': { opacity: '1', transform: 'scale(1)' },
  			},
  			'press': {
  				'0%': { transform: 'scale(1)' },
  				'50%': { transform: 'scale(0.97)' },
  				'100%': { transform: 'scale(1)' },
  			},
  			'shimmer': {
  				'0%': { backgroundPosition: '-200% 0' },
  				'100%': { backgroundPosition: '200% 0' },
  			},
  			'pulse-subtle': {
  				'0%, 100%': { opacity: '1' },
  				'50%': { opacity: '0.5' },
  			},
  			'stagger-in': {
  				from: { opacity: '0', transform: 'translateY(12px)' },
  				to: { opacity: '1', transform: 'translateY(0)' },
  			},
  		},
  		animation: {
  			'glow-word': 'glow-word 1.5s ease-in-out infinite',
  			'fade-in': 'fade-in 200ms ease-out',
  			'fade-out': 'fade-out 150ms ease-in',
  			'slide-up': 'slide-up 250ms ease-out',
  			'slide-down': 'slide-down 250ms ease-out',
  			'scale-in': 'scale-in 200ms ease-out',
  			'scale-out': 'scale-out 150ms ease-in',
  			'spring-in': 'spring-in 350ms cubic-bezier(0.34, 1.56, 0.64, 1)',
  			'press': 'press 150ms ease-in-out',
  			'shimmer': 'shimmer 1.5s infinite',
  			'pulse-subtle': 'pulse-subtle 2s ease-in-out infinite',
  			'stagger-in': 'stagger-in 300ms ease-out both',
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
