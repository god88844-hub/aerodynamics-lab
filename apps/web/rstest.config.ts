import { defineConfig } from '@rstest/core'
import { pluginReact } from '@rsbuild/plugin-react'

export default defineConfig({
  plugins: [pluginReact()],
  testEnvironment: 'jsdom',
  include: ['src/**/*.{test,spec}.{ts,tsx}'],
})
