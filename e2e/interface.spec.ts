import {test,expect} from '@playwright/test';
import path from 'node:path';

test('responsive board, exact object selection, layers and accessible dialogs',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'New project',exact:true}).click();
 await page.locator('input[type=file]').first().setInputFiles(['fieldnode.kicad_pcb','fieldnode.kicad_pro'].map(f=>path.resolve('fixtures/fieldnode',f)));
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
 expect(await page.locator('.r2-board [data-highlight-status=selected]').count()).toBeGreaterThan(0);
 await page.getByRole('button',{name:'Layers',exact:true}).click();await page.getByLabel('F.Cu',{exact:true}).uncheck();
 await expect(page.locator('.board-svg image')).toHaveCount(3); await page.getByLabel('F.Cu',{exact:true}).check();
 await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Layers',exact:true})).toBeFocused();
 await page.screenshot({path:'screenshots/review-v2-desktop.png',fullPage:true});
 for(const width of [1440,1024,768,390,360]){
  await page.setViewportSize({width,height:1000});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
 }
 await page.locator('.r2-mobile-tabs').getByRole('button',{name:'Issues',exact:true}).click();
 await expect(page.getByLabel('Search findings, nets or components')).toBeVisible();
 await page.getByLabel('Search findings, nets or components').fill('track width');
 await page.locator('.r2-issue').first().click();
 await expect(page.locator('.r2-board')).toBeVisible();
 await page.getByRole('button',{name:'Inspect evidence',exact:true}).click();
 await expect(page.locator('.r2-inspector h2')).toHaveText('Track width below configured minimum');
 await page.screenshot({path:'screenshots/review-v2-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'New project',exact:true}).click();
 await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
});
