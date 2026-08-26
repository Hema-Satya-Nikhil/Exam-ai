import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './features/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--background) / <alpha-value>)',
        foreground: 'rgb(var(--foreground) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        glass: 'rgb(var(--glass) / <alpha-value>)'
      },
      boxShadow: {
        glass: '0 24px 80px rgba(15, 23, 42, 0.18)'
      },
      backdropBlur: {
        glass: '24px'
      },
      borderRadius: {
        '4xl': '2rem'
      }
    }
  },
  plugins: []
};

export default config;
