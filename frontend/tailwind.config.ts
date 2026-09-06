import type { Config } from 'tailwindcss';

/**
 * ExamCraft AI — centralized design tokens (Phase 1).
 * Semantic colors reference CSS variables defined in app/globals.css so the
 * palette stays in one place. Typography/spacing/radius/elevation/motion are
 * defined here so every future page composes the same system.
 */
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
        // Surfaces & structure
        background: 'rgb(var(--background) / <alpha-value>)',
        'background-deep': 'rgb(var(--background-deep) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        'surface-elevated': 'rgb(var(--surface-elevated) / <alpha-value>)',
        'surface-glass': 'rgb(var(--surface-glass) / <alpha-value>)',
        line: 'rgb(var(--border) / <alpha-value>)',
        'text-primary': 'rgb(var(--text-primary) / <alpha-value>)',
        'text-secondary': 'rgb(var(--text-secondary) / <alpha-value>)',
        'text-muted': 'rgb(var(--text-muted) / <alpha-value>)',
        // Brand & feedback
        primary: {
          DEFAULT: 'rgb(var(--primary) / <alpha-value>)',
          hover: 'rgb(var(--primary-hover) / <alpha-value>)',
          soft: 'rgb(var(--primary-soft) / <alpha-value>)'
        },
        success: {
          DEFAULT: 'rgb(var(--success) / <alpha-value>)',
          soft: 'rgb(var(--success-soft) / <alpha-value>)'
        },
        warning: {
          DEFAULT: 'rgb(var(--warning) / <alpha-value>)',
          soft: 'rgb(var(--warning-soft) / <alpha-value>)'
        },
        danger: {
          DEFAULT: 'rgb(var(--danger) / <alpha-value>)',
          soft: 'rgb(var(--danger-soft) / <alpha-value>)'
        },
        info: {
          DEFAULT: 'rgb(var(--info) / <alpha-value>)',
          soft: 'rgb(var(--info-soft) / <alpha-value>)'
        },
        // Legacy aliases (pre-Phase-1 pages) — do not use in new work
        glass: 'rgb(255 255 255 / <alpha-value>)'
      },

      // 8px-based spacing scale (named tokens on top of the default scale)
      spacing: {
        'space-1': '0.25rem',   // 4px  — micro (icon gaps)
        'space-2': '0.5rem',    // 8px
        'space-3': '0.75rem',   // 12px
        'space-4': '1rem',      // 16px — base unit
        'space-5': '1.5rem',    // 24px
        'space-6': '2rem',      // 32px
        'space-7': '2.5rem',    // 40px
        'space-8': '3rem',      // 48px
        'space-9': '4rem',      // 64px
        'space-10': '6rem'      // 96px — section rhythm
      },

      borderRadius: {
        sm: '0.375rem',   // 6px  — badges, chips, small controls
        DEFAULT: '0.5rem',// 8px  — inputs, buttons
        md: '0.625rem',   // 10px
        lg: '0.75rem',    // 12px — cards, modals
        xl: '1rem',       // 16px — large cards
        pill: '9999px'    // pills, status badges
      },

      boxShadow: {
        none: 'none',
        low: '0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.06)',
        medium: '0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.05)',
        high: '0 16px 40px rgba(15, 23, 42, 0.14), 0 4px 12px rgba(15, 23, 42, 0.08)',
        'glass-soft': '0 18px 50px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
        // Legacy (pre-Phase-1 pages) — do not use in new work
        glass: '0 24px 80px rgba(15, 23, 42, 0.18)'
      },

      fontSize: {
        display: ['2.5rem', { lineHeight: '1.1', fontWeight: '700', letterSpacing: '-0.02em' }],
        heading: ['1.75rem', { lineHeight: '1.25', fontWeight: '600', letterSpacing: '-0.01em' }],
        'section-heading': ['1.25rem', { lineHeight: '1.4', fontWeight: '600' }],
        body: ['0.9375rem', { lineHeight: '1.6', fontWeight: '400' }],
        small: ['0.875rem', { lineHeight: '1.5', fontWeight: '400' }],
        label: ['0.8125rem', { lineHeight: '1.4', fontWeight: '500' }],
        metadata: ['0.75rem', { lineHeight: '1.4', fontWeight: '400' }]
      },

      // Motion tokens — restrained by design
      transitionDuration: {
        micro: '150ms',
        panel: '250ms'
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.2, 0, 0, 1)',
        entrance: 'cubic-bezier(0.16, 1, 0.3, 1)'
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' }
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97) translateY(4px)' },
          to: { opacity: '1', transform: 'scale(1) translateY(0)' }
        },
        'slide-in-left': {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' }
        }
      },
      animation: {
        'fade-in': 'fade-in var(--motion-panel, 250ms) cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scale-in var(--motion-panel, 250ms) cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-left': 'slide-in-left var(--motion-panel, 250ms) cubic-bezier(0.16, 1, 0.3, 1)'
      },

      // Legacy (pre-Phase-1 pages) — do not use in new work
      backdropBlur: {
        glass: '18px'
      }
    }
  },
  plugins: []
};

export default config;
