/**
 * IAnalisys Design Tokens
 * Baseado na identidade visual de www.ianalisys.com.br
 */

export const colors = {
  // Brand
  brand: {
    black: '#000000',
    white: '#FFFFFF',
    dark: '#171717',
  },

  // Primary — azul institucional
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

  // Neutral — escala de cinzas
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

  // Semantic
  success: {
    bg: '#F0FCE7',
    border: '#A6D963',
    text: '#1A8917',
  },
  info: {
    bg: '#F0F9FF',
    border: '#BFDBFE',
    text: '#2563EB',
  },
  warning: {
    bg: '#FFFBF0',
    border: '#FCD34D',
    text: '#D97706',
  },
  error: {
    bg: '#FEF2F2',
    border: '#FECACA',
    text: '#DC2626',
  },
} as const;

export const typography = {
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
    xs: ['0.75rem', { lineHeight: '1rem' }],       // 12px
    sm: ['0.8125rem', { lineHeight: '1.25rem' }],   // 13px — base do site
    base: ['0.875rem', { lineHeight: '1.375rem' }], // 14px
    md: ['1rem', { lineHeight: '1.5rem' }],          // 16px
    lg: ['1.125rem', { lineHeight: '1.75rem' }],     // 18px
    xl: ['1.25rem', { lineHeight: '1.75rem' }],      // 20px
    '2xl': ['1.5rem', { lineHeight: '2rem' }],       // 24px
    '3xl': ['1.875rem', { lineHeight: '2.25rem' }],  // 30px
    '4xl': ['2.25rem', { lineHeight: '2.5rem' }],    // 36px
  },
  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
} as const;

export const spacing = {
  px: '1px',
  0: '0',
  0.5: '0.125rem',  // 2px
  1: '0.25rem',      // 4px
  1.5: '0.375rem',   // 6px
  2: '0.5rem',       // 8px
  3: '0.75rem',      // 12px
  4: '1rem',         // 16px — unidade base
  5: '1.25rem',      // 20px
  6: '1.5rem',       // 24px
  8: '2rem',         // 32px
  10: '2.5rem',      // 40px
  12: '3rem',        // 48px
  16: '4rem',        // 64px
  20: '5rem',        // 80px
  24: '6rem',        // 96px
} as const;

export const borderRadius = {
  none: '0',
  sm: '0.25rem',     // 4px — botões
  DEFAULT: '0.5rem', // 8px — cards, inputs, toasts
  lg: '0.75rem',     // 12px
  xl: '1rem',        // 16px
  full: '9999px',    // circular
} as const;

export const shadows = {
  sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
  DEFAULT: '0 4px 12px rgba(0, 0, 0, 0.1)',
  md: '0 4px 16px rgba(0, 0, 0, 0.12)',
  lg: '0 8px 24px rgba(0, 0, 0, 0.15)',
  focus: '0 4px 12px rgba(0, 0, 0, 0.1), 0 0 0 2px rgba(37, 99, 235, 0.2)',
} as const;

export const transitions = {
  fast: '150ms ease',
  DEFAULT: '200ms ease',
  slow: '400ms ease',
} as const;

export const zIndex = {
  dropdown: 50,
  sticky: 100,
  navbar: 200,
  modal: 300,
  toast: 400,
  tooltip: 500,
} as const;
