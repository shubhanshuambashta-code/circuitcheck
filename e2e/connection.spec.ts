import {test,expect} from '@playwright/test';
import path from 'node:path';

test('upload connection failure explains recovery and allows retry',async({page})=>{
 let created:string|undefined;
 try{
  await page.goto('/');
  await page.getByRole('button',{name:'Upload project',exact:true}).first().click();
  await page.route('**/api/projects',route=>route.request().method()==='POST'?route.abort('failed'):route.continue());
  const files=['drc.kicad_pcb','drc.kicad_pro'].map(file=>path.resolve('fixtures/drc',file));
  await page.locator('input[type=file]').setInputFiles(files);
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Cannot reach the local server.');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('alert')).not.toContainText('Failed to fetch');
  await page.unroute('**/api/projects');
  const response=page.waitForResponse(r=>r.url().endsWith('/api/projects')&&r.request().method()==='POST');
  await page.locator('input[type=file]').setInputFiles(files);
  const upload=await response;expect(upload.status()).toBe(202);created=(await upload.json()).project_id;
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByText('Checks completed',{exact:true})).toBeVisible({timeout:60000});
  await expect(page.locator('.findings-table')).toContainText('Track width below configured minimum');
 }finally{
  if(created){const deleted=await page.request.delete('/api/projects/'+created,{headers:{'X-CircuitCheck':'1'}});expect(deleted.ok()).toBeTruthy()}
 }
});
