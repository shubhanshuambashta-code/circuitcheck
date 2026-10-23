import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({mode})=>({
 plugins:[react(),tailwindcss()],
 base:mode==='pages'?'/circuitcheck/':'/',
 build:{outDir:mode==='pages'?'dist-pages':'dist'},
 server:{port:5173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000'},watch:{ignored:['**/data/**','**/test-results/**','**/playwright-report/**','**/screenshots/**','**/dist-pages/**']}}
}));
