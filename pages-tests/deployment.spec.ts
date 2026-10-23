import {test,expect} from '@playwright/test';

for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
 test(`Pages preview works without an API at ${viewport.width}px`,async({page})=>{
  await page.setViewportSize(viewport);
  const errors:string[]=[],failed:string[]=[],apiRequests:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)failed.push(`${response.status()} ${response.url()}`)});
  page.on('request',request=>{if(new URL(request.url()).pathname.includes('/api/'))apiRequests.push(request.url())});
  await page.goto('./');
  await expect(page.getByRole('heading',{name:'Understand the finding. Check the correction.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Run analysis in the local app.'})).toBeVisible();
  const image=page.getByRole('img',{name:/CircuitCheck local application screenshot/});
  await expect(image).toBeVisible();
  await expect.poll(()=>image.evaluate(el=>(el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await page.getByRole('link',{name:'Run CircuitCheck',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Review your own board locally.'})).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.getByRole('link',{name:'Download test projects'}).click();
  await expect(page.getByRole('heading',{name:'Check the checker.'})).toBeVisible();
  expect(page.url()).toContain('/circuitcheck/test-files/');
  for(const name of ['track-width-before.zip','track-width-corrected.zip','empty-board-outline.zip']){
   const response=await page.request.get(new URL(name,page.url()).href);
   expect(response.status()).toBe(200);
   const bytes=await response.body();expect(bytes.subarray(0,2).toString()).toBe('PK');
  }
  await page.getByRole('link',{name:'Back to CircuitCheck'}).click();
  await expect(page.getByRole('heading',{name:'Understand the finding. Check the correction.'})).toBeVisible();
  expect(errors).toEqual([]);expect(failed).toEqual([]);expect(apiRequests).toEqual([]);
 });
}
