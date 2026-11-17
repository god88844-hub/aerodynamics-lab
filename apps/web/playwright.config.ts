import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    actionTimeout: 10_000,
    launchOptions: {
      // The local test stack renders its Three.js viewport without a hardware GPU.
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },
})
