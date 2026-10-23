import {test,expect} from '@playwright/test';
import path from 'node:path';
import {readFileSync} from 'node:fs';
const fixture=(name:string,file:string)=>path.resolve('fixtures',name,file);
const upload=async(page:any,name:string,files:string[])=>{
 await page.getByRole('button',{name:'Upload project',exact:true}).first().click();
 await page.locator('input[type=file]').setInputFiles(files.map(f=>fixture(name,f)));
 await expect(page.getByRole('dialog')).toHaveCount(0);
};
test('empty workspace, upload errors and keyboard dialog control',async({page})=>{
 await page.goto('/');await expect(page.getByText('Start a design review')).toBeVisible();
 await page.getByRole('button',{name:'Upload project',exact:true}).first().click();
 await page.locator('input[type=file]').setInputFiles({name:'drawing.stl',mimeType:'application/octet-stream',buffer:Buffer.from('solid unsupported')});
 await expect(page.getByRole('alert')).toContainText('unsupported file type');
 await page.screenshot({path:'screenshots/upload-error.png',fullPage:true});
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.keyboard.press('Control+o');await expect(page.getByRole('dialog')).toBeVisible();
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
});
test('real upload, evidence, guarded repair, recheck, compare, download and undo',async({page})=>{
 await page.goto('/');await upload(page,'drc',['drc.kicad_pcb','drc.kicad_pro']);
 await expect(page.getByText('Checks completed',{exact:true})).toBeVisible();
 await expect(page.locator('.details-panel h2')).toHaveText('Track width below configured minimum');
 await expect(page.locator('.measurement')).toContainText('0.25 mm');
 await expect(page.locator('.finding-marker.selected')).toHaveCount(1);
 const box=await page.locator('.board-svg').getAttribute('viewBox');
 await page.getByLabel('Zoom in',{exact:true}).click();expect(await page.locator('.board-svg').getAttribute('viewBox')).not.toBe(box);
 await page.getByLabel('Fit design',{exact:true}).click();expect(await page.locator('.board-svg').getAttribute('viewBox')).toBe(box);
 await page.getByPlaceholder('Search findings…').fill('nothing-matches-this-query');
 await expect(page.getByText('No findings match these filters.')).toBeVisible();await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await page.getByRole('button',{name:'Ask',exact:true}).click();await page.getByRole('button',{name:'Which rule triggered this?'}).click();
 await expect(page.locator('.message.assistant')).toContainText('actual 0.1500 mm');
 await page.getByRole('button',{name:'Finding details',exact:true}).click();
 await page.getByRole('button',{name:'Preview change',exact:true}).click();
 await expect(page.getByText('The targeted violation was not reported in the proposed copy.',{exact:false})).toBeVisible({timeout:60000});
 await page.waitForLoadState('networkidle');await page.screenshot({path:'screenshots/repair-preview.png',fullPage:true});
 await page.getByRole('button',{name:'Apply change & recheck'}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Checks completed',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.locator('.revision-row')).toHaveCount(2);
 await page.getByRole('button',{name:'Compare',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('1 resolved');await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Export',exact:true}).click();const exported=page.waitForEvent('download');await page.getByRole('button',{name:'Current project .zip'}).click();expect((await exported).suggestedFilename()).toMatch(/\.zip$/);
 await page.getByRole('button',{name:'Restore previous revision'}).click();await expect(page.getByText('Checks completed',{exact:true})).toBeVisible();
 await page.locator('.bottom-tabs button').filter({hasText:'Findings'}).click();await expect(page.locator('.findings-table')).toContainText('Track width below configured minimum');
});
test('clean and partial analysis do not overclaim coverage',async({page})=>{
 await page.goto('/');await upload(page,'valid',['valid.kicad_pcb','valid.kicad_pro']);await expect(page.getByText('Checks completed',{exact:true})).toBeVisible();
 await expect(page.getByText('No violations found in the checks performed.')).toBeVisible();
 await page.getByRole('button',{name:'Check coverage',exact:true}).click();await expect(page.locator('.coverage-list')).toContainText('Not checked');
 await page.screenshot({path:'screenshots/clean-checks.png',fullPage:true});
 await page.getByRole('button',{name:'New project',exact:true}).click();await page.locator('input[type=file]').setInputFiles(fixture('valid','valid.kicad_pcb'));
 await expect(page.locator('.alert').filter({hasText:'Partial analysis.'})).toBeVisible({timeout:60000});
 await expect(page.locator('.primary').filter({hasText:'Preview change'})).toHaveCount(0);
});
test('engine failure stays a failure in the interface',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Upload project',exact:true}).first().click();
 await page.locator('input[type=file]').setInputFiles({name:'broken.kicad_pcb',mimeType:'text/plain',buffer:Buffer.from('(kicad_pcb (version 20241229) (generator "test") (unknown_invalid_token 1))')});
 await expect(page.getByText('Analysis did not complete.',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.getByText('No violations found in the checks performed.')).toHaveCount(0);await page.screenshot({path:'screenshots/analysis-failure.png',fullPage:true});
});
test('example review, layers, selection and responsive panels',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Explore the example project'}).click();
 await expect(page.getByText('Checks completed',{exact:true})).toBeVisible({timeout:60000});
 await page.waitForLoadState('networkidle');await page.screenshot({path:'screenshots/workspace-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Layers',exact:true}).click();await page.getByLabel('F.Cu',{exact:true}).uncheck();
 await expect(page.locator('.board-svg image')).toHaveCount(3);await page.getByLabel('F.Cu',{exact:true}).check();await page.getByRole('button',{name:'Layers',exact:true}).click();
 await page.setViewportSize({width:390,height:844});await expect(page.locator('body')).toHaveJSProperty('scrollWidth',390);
 await page.screenshot({path:'screenshots/workspace-mobile.png',fullPage:true});
 await page.locator('.mobile-panel-tabs').getByRole('button',{name:/Findings/}).click();await page.getByLabel('Filter findings').selectOption('repair');
 await page.locator('.finding-row-button').first().click();await expect(page.locator('.details-panel h2')).toBeVisible();
 await expect(page.getByRole('button',{name:'Preview change',exact:true})).toBeVisible();await page.screenshot({path:'screenshots/details-mobile.png',fullPage:true});
});

test('long native filenames stay readable without horizontal overflow',async({page})=>{
 const name='environmental-sensor-interface_board-revision-2026-10-23-for-manufacturing-review';
 await page.goto('/');await page.getByRole('button',{name:'Upload project',exact:true}).first().click();
 await page.locator('input[type=file]').setInputFiles([
  {name:name+'.kicad_pcb',mimeType:'text/plain',buffer:readFileSync(fixture('valid','valid.kicad_pcb'))},
  {name:name+'.kicad_pro',mimeType:'application/json',buffer:readFileSync(fixture('valid','valid.kicad_pro'))}
 ]);
 await expect(page.getByText('Checks completed',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.getByRole('heading',{level:1})).toHaveText(name);
 await expect(page.locator('body')).toHaveJSProperty('scrollWidth',1440);
 await page.setViewportSize({width:390,height:844});await expect(page.locator('body')).toHaveJSProperty('scrollWidth',390);
});
