import { execFile } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { expect, test } from '@playwright/test'

const run = promisify(execFile)
const root = fileURLToPath(new URL('../../../', import.meta.url))

function compose(...args: string[]) {
  return run('docker', ['compose', '--project-name', 'aeroforge-e2e', ...args], {
    cwd: root,
    timeout: 65_000,
  })
}

test('packaged UI edits a design, runs the solver, and reloads saved data after API replacement', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))

  await expect.poll(async () => (await request.get('/api/health')).status(), {
    timeout: 15_000,
  }).toBe(200)
  const publicEvidence = await request.get('/api/components/public-evidence')
  expect(publicEvidence.status()).toBe(200)
  expect(await publicEvidence.json()).toMatchObject({
    quadplane_battery_audit: { quality: { rows_verified: 1442 } },
    model_physically_validated_by_these_public_sources: false,
  })
  const referenceResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === '/api/designs/reference',
  )
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'AeroForge', exact: true })).toBeVisible()
  await expect(page.getByText(/^API v/)).toBeVisible()
  const reference = await referenceResponse
  expect(reference.ok()).toBeTruthy()

  const name = page.getByRole('textbox', { name: 'name', exact: true })
  await expect(name).toHaveValue((await reference.json()).snapshot.name)
  await expect(page.getByLabel('Saved designs')).toBeVisible()

  const label = `E2E ${randomUUID()}`
  await name.fill(label)
  const saveResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === '/api/designs' && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Save as new design' }).click()
  const savedResponse = await saveResponse
  expect(savedResponse.ok()).toBeTruthy()
  const saved = await savedResponse.json()
  expect(saved).toMatchObject({ name: label, snapshot: { name: label } })
  expect(saved.id).toBeGreaterThan(0)
  const saveDesign = page.getByRole('button', { name: 'Save design', exact: true })
  await expect(saveDesign).toBeEnabled()

  const revised = `${label} revised`
  await name.fill(revised)
  const updateResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/designs/${saved.id}` && response.request().method() === 'PUT',
  )
  await saveDesign.click()
  const updated = await updateResponse
  expect(updated.ok()).toBeTruthy()
  expect(await updated.json()).toMatchObject({ id: saved.id, name: revised })
  await expect(name).toHaveValue(revised)

  await page.getByRole('combobox', { name: 'scenario', exact: true }).selectOption('hover-ideal')
  const simulationResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/designs/${saved.id}/simulate`
    && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '▶ Simulate' }).click()
  const simulation = await simulationResponse
  expect(simulation.ok()).toBeTruthy()
  expect(simulation.request().postDataJSON()).toMatchObject({ scenario: 'hover-ideal' })
  const result = await simulation.json()
  expect(result).toMatchObject({
    design_id: saved.id,
    scenario: expect.stringMatching(/^hover-ideal(?: |$)/),
    status: 'completed',
  })
  expect(result.simulation_id).toBeGreaterThan(0)
  await expect(page.getByRole('heading', { name: 'Trustworthiness' })).toBeVisible()
  await expect(page.getByText(result.trustworthiness.verdict, { exact: true })).toBeVisible()

  const apiBefore = (await compose('ps', '-q', 'api')).stdout.trim()
  const webBefore = (await compose('ps', '-q', 'web')).stdout.trim()
  expect(apiBefore).not.toBe('')
  expect(webBefore).not.toBe('')
  await compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '45', 'api')
  expect((await compose('ps', '-q', 'api')).stdout.trim()).not.toBe(apiBefore)
  expect((await compose('ps', '-q', 'web')).stdout.trim()).toBe(webBefore)
  await expect.poll(async () => (await request.get('/api/health')).status(), {
    timeout: 15_000,
  }).toBe(200)

  await page.reload()
  const savedDesigns = page.getByLabel('Saved designs')
  await expect(savedDesigns.getByRole('option', { name: `#${saved.id} ${revised}` })).toHaveCount(1)
  await savedDesigns.selectOption(String(saved.id))
  await expect(name).toHaveValue(revised)

  const storedRun = await request.get(`/api/simulations/${result.simulation_id}`)
  expect(storedRun.ok()).toBeTruthy()
  expect(await storedRun.json()).toMatchObject(result)
  expect(errors).toEqual([])
})
