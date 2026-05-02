/** @type {import('tailwindcss').Config} */
import ianalisysPreset from './src/theme/tailwind.preset.js';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  presets: [ianalisysPreset],
  plugins: [],
};
