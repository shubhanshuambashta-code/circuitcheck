import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./pages-tests',timeout:30000,workers:1,
 use:{baseURL:'http://127.0.0.1:4173/circuitcheck/',channel:process.env.PW_CHANNEL||'chrome',trace:'retain-on-failure',screenshot:'only-on-failure'},
 webServer:{command:'npm run preview -- --mode pages --outDir dist-pages --port 4173 --strictPort',url:'http://127.0.0.1:4173/circuitcheck/',timeout:30000,reuseExistingServer:!process.env.CI},
 reporter:[['list']]
});
