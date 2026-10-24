import {test,expect,Page} from '@playwright/test';
import path from 'node:path';
const fixture=(name:string,file:string)=>path.resolve('fixtures',name,file);
async function upload(page:Page,name:string,files:string[]){
 await page.getByRole('button',{name:'New project',exact:true}).click();
 await page.locator('input[type=file]').first().setInputFiles(files.map(f=>fixture(name,f)));
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
}

test('native finding, exact track highlight, review notes, approved repair and revision comparison',async({page})=>{
 await page.goto('/');await upload(page,'drc',['drc.kicad_pcb','drc.kicad_pro']);
 await expect(page.locator('.r2-inspector h2')).toHaveText('Track width below configured minimum');
 await expect(page.locator('.r2-measurements')).toContainText('0.15 mm');
 await expect(page.locator('.r2-measurements')).toContainText('0.25 mm');
 expect(await page.locator('[data-highlight-status=selected]').count()).toBeGreaterThan(0);
 const ids=await page.locator('[data-highlight-status=selected]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-object-id')));
 expect(ids[0]).toMatch(/^[a-f0-9-]{36}$/); await expect(page.locator('[data-highlight-status=selected] polyline').first()).toHaveAttribute('points','65,65 85,65');
 await page.getByRole('button',{name:/Highlight net GND/}).click();
 expect(await page.locator('[data-highlight-status=selected]').count()).toBeGreaterThan(0);
 await page.locator('.r2-inspector-tabs').getByRole('button',{name:'Review',exact:true}).click();
 await page.getByLabel('Reason / review comment').fill('QA: inspect the native width correction and retain this review.');
 await page.getByRole('button',{name:'Save review note'}).click();
 await expect(page.locator('.r2-notes')).toContainText('QA: inspect');
 await page.locator('.r2-inspector-tabs').getByRole('button',{name:'Explain',exact:true}).click();
 await page.getByLabel('Question about this evidence').fill('Which rule triggered this?');
 await page.getByRole('button',{name:'Explain evidence',exact:true}).click();
 await expect(page.locator('.r2-answer')).toContainText('actual 0.1500 mm');
 await page.locator('.r2-inspector-tabs').getByRole('button',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Review proposed change'}).click();
 await expect(page.getByRole('dialog').locator('.r2-verification')).toBeVisible({timeout:60000});
 const apply=page.getByRole('button',{name:'Apply approved copy & recheck'});
 await expect(apply).toBeDisabled();
 await page.getByRole('dialog').screenshot({path:'screenshots/review-v2-repair.png'});
 await page.getByRole('checkbox',{name:/I reviewed this exact dimension/}).check();
 await expect(apply).toBeEnabled();await apply.click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.locator('.r2-change-groups').getByRole('button',{name:/^Resolved/})).toContainText('1');
 await expect(page.locator('.r2-comparison-scope')).toContainText('Rules: unchanged');
 await page.locator('.r2-change-list>button').first().click();
 await page.locator('.r2-inspector-tabs').getByRole('button',{name:/Review/}).click();
 await expect(page.locator('.r2-notes')).toContainText('QA: inspect');
 await page.getByRole('button',{name:'Download',exact:true}).click();
 const exported=page.waitForEvent('download');await page.getByRole('button',{name:'Current native project',exact:true}).click();
 expect((await exported).suggestedFilename()).toMatch(/\.zip$/);
 await page.getByRole('button',{name:'Download',exact:true}).click();await page.getByRole('button',{name:'Restore previous revision'}).click();
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
 await page.getByRole('button',{name:'Design review',exact:true}).click();
 await expect(page.locator('.r2-issue-list')).toContainText('Track width below configured minimum');
});

test('upload revision B into the same project and compare stable findings',async({page})=>{
 await page.goto('/');await upload(page,'drc',['drc.kicad_pcb','drc.kicad_pro']);
 await page.getByRole('button',{name:'Upload revision B',exact:true}).first().click();
 await page.locator('input[type=file]').first().setInputFiles(['drc.kicad_pcb','drc.kicad_pro'].map(f=>fixture('corrected',f)));
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.locator('.r2-change-groups').getByRole('button',{name:/^Resolved/})).toContainText('1');
 await expect(page.locator('.r2-comparison-boards .board-svg')).toHaveCount(2);
 await page.screenshot({path:'screenshots/review-v2-comparison.png',fullPage:true});
});

test('coverage distinguishes checked zero, not checked, partial and failed',async({page})=>{
 await page.goto('/');await upload(page,'valid',['valid.kicad_pcb','valid.kicad_pro']);
 await page.getByRole('button',{name:'Check coverage',exact:true}).click();
 const clearance=page.getByRole('row').filter({hasText:'Copper clearance'});
 await expect(clearance).toContainText('checked');await expect(clearance).toContainText('No issues found');
 await expect(page.getByRole('row').filter({hasText:'Schematic electrical rules'})).toContainText('not checked');
 await expect(page.getByRole('row').filter({hasText:'Component voltage / power ratings'})).toContainText('not checked');
 await page.screenshot({path:'screenshots/review-v2-coverage.png',fullPage:true});
 await page.getByRole('button',{name:'New project',exact:true}).click();
 await page.locator('input[type=file]').first().setInputFiles(fixture('valid','valid.kicad_pcb'));
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Partial analysis',{exact:true})).toBeVisible({timeout:60000});
 await page.getByRole('button',{name:'Check coverage',exact:true}).click();
 await expect(page.getByRole('row').filter({hasText:'Copper clearance'})).toContainText('partial');
 await page.getByRole('button',{name:'New project',exact:true}).click();
 await page.locator('input[type=file]').first().setInputFiles({name:'broken.kicad_pcb',mimeType:'text/plain',buffer:Buffer.from('(kicad_pcb (version 20241229) (generator "test") (unknown_invalid_token 1))')});
 await expect(page.getByText('Analysis failed; no clean result was established.')).toBeVisible({timeout:60000});
 await expect(page.locator('.r2-summary')).toHaveCount(0);
});

test('custom fabrication profile creates a revision and measurable native findings',async({page})=>{
 await page.goto('/');await upload(page,'drc',['drc.kicad_pcb','drc.kicad_pro']);
 await page.locator('.r2-profile-link').click();await page.getByRole('button',{name:'Custom rules',exact:true}).click();
 await page.getByLabel('Profile name', {exact:true}).fill('QA fabrication profile');
 await page.getByLabel('Minimum track width (mm)',{exact:true}).fill('0.4');
 await page.getByRole('button',{name:'Create profile revision & check'}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByText('Engineering checks completed',{exact:true})).toBeVisible({timeout:60000});
 await expect(page.getByRole('row').filter({hasText:'Fabrication · track width'})).toContainText('checked');
 await page.getByRole('button',{name:'Revision comparison',exact:true}).click();
 await expect(page.locator('.r2-comparison-scope')).toContainText('Profile: changed');
 await expect(page.locator('.r2-change-groups').getByRole('button',{name:/No longer reported/})).toBeVisible();
});
