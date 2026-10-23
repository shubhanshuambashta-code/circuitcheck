import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:90000,expect:{timeout:20000},workers:1,fullyParallel:false,
 use:{baseURL:process.env.PW_BASE_URL||'http://127.0.0.1:8000',viewport:{width:1440,height:1000},channel:process.env.PW_CHANNEL||'chrome',trace:'retain-on-failure',screenshot:'only-on-failure'},
 reporter:[['list'],['html',{open:'never'}]]});
