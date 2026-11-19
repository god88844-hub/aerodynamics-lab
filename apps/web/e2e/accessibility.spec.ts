import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('workspace supports keyboard editing and readable expanded panels', async ({ page }, testInfo) => {
  test.setTimeout(240_000)
  await page.goto('/')
  await expect(page.getByLabel('Saved designs')).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to design controls' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('complementary', { name: 'Design and simulation' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Enable 3D translate handles')).toBeFocused()
  const component = page.getByLabel('Selected component', { exact: true })
  await expect(component.locator('option[value="battery"]')).toHaveCount(1)
  await component.focus()
  await component.press('Home')
  const batteryIndex = await component.locator('option[value="battery"]').evaluate(element => (element as HTMLOptionElement).index)
  for (let index = 0; index < batteryIndex; index++) await component.press('ArrowDown')
  await component.press('Enter')
  await expect(component).toHaveValue('battery')
  const mass = page.getByLabel('Component mass [kg]', { exact: true })
  await mass.focus()
  const previous = Number(await mass.inputValue())
  await mass.press('ArrowUp')
  await expect.poll(async () => Number(await mass.inputValue())).toBeGreaterThan(previous)
  await page.getByRole('button', { name: 'Undo', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(mass).toHaveValue(String(previous))

  for (const summary of await page.locator('summary').all()) {
    if (!await summary.evaluate(element => (element.parentElement as HTMLDetailsElement).open)) {
      await summary.click()
    }
  }
  const failures = new Map<string, unknown>()
  const scans = []
  // Contrast checks need each scrollable panel's content in the viewport.
  for (const panel of await page.getByRole('complementary').all()) {
    const dimensions = await panel.evaluate(element => ({
      height: element.clientHeight, total: element.scrollHeight,
    }))
    for (let top = 0; top < dimensions.total; top += Math.max(1, dimensions.height * 0.75)) {
      await panel.evaluate((element, offset) => { element.scrollTop = offset }, top)
      const result = await new AxeBuilder({ page }).analyze()
      scans.push({ top, violations: result.violations, incomplete: result.incomplete })
      for (const violation of result.violations) {
        for (const node of violation.nodes) {
          const key = JSON.stringify([violation.id, node.target])
          failures.set(key, { rule: violation.id, target: node.target, reason: node.failureSummary })
        }
      }
    }
  }
  await testInfo.attach('accessibility-scans', {
    body: JSON.stringify(scans), contentType: 'application/json',
  })
  expect([...failures.values()]).toEqual([])
})
