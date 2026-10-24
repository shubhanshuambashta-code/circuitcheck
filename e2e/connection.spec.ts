import {test,expect} from '@playwright/test';
import path from 'node:path';
test('connection failure explains recovery and upload can be retried',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'New project',exact:true}).click();
 await page.route('**/api/projects',route=>route.request().method()==='POST'?route.abort('failed'):route.continue());
 const files=['drc.kicad_pcb','drc.kicad_pro'].map(f=>path.resolve('fixtures/drc',f));
 await page.locator('input[type=file]').first().setInputFiles(files);
 await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Cannot reach the local server.');
 await page.unroute('**/api/projects');await page.locator('input[type=file]').first().setInputFiles(files);
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
});
