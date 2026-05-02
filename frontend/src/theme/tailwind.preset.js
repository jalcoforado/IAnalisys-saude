/**
 * IAnalisys Tailwind Preset
 * Estende o Tailwind com os tokens da marca
 */

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {
        brand: {
          black: '#000000',
          white: '#FFFFFF',
          dark: '#171717',
        },
        primary: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        neutral: {
          50: '#FAFAFA',
          100: '#F5F5F5',
          200: '#E5E5E5',
          300: '#D4D4D4',
          400: '#A3A3A3',
          500: '#737373',
          600: '#525252',
          700: '#404040',
          800: '#262626',
          900: '#171717',
        },
        success: {
          bg: '#F0FCE7',
          border: '#A6D963',
          text: '#1A8917',
          DEFAULT: '#1A8917',
        },
        info: {
          bg: '#F0F9FF',
          border: '#BFDBFE',
          text: '#2563EB',
          DEFAULT: '#2563EB',
        },
        warning: {
          bg: '#FFFBF0',
          border: '#FCD34D',
          text: '#D97706',
          DEFAULT: '#D97706',
        },
        error: {
          bg: '#FEF2F2',
          border: '#FECACA',
          text: '#DC2626',
          DEFAULT: '#DC2626',
        },
      },

      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'Noto Sans',
          'sans-serif',
        ],
      },

      fontSize: {
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.375rem' }],
        md: ['1rem', { lineHeight: '1.5rem' }],
        lg: ['1.125rem', { lineHeight: '1.75rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },

      borderRadius: {
        sm: '0.25rem',
        DEFAULT: '0.5rem',
        lg: '0.75rem',
        xl: '1rem',
      },

      boxShadow: {
        sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
        DEFAULT: '0 4px 12px rgba(0, 0, 0, 0.1)',
        md: '0 4px 16px rgba(0, 0, 0, 0.12)',
        lg: '0 8px 24px rgba(0, 0, 0, 0.15)',
        focus: '0 4px 12px rgba(0, 0, 0, 0.1), 0 0 0 2px rgba(37, 99, 235, 0.2)',
      },

      transitionDuration: {
        fast: '150ms',
        DEFAULT: '200ms',
        slow: '400ms',
      },

      zIndex: {
        dropdown: '50',
        sticky: '100',
        navbar: '200',
        modal: '300',
        toast: '400',
        tooltip: '500',
      },
    },
  },
};
