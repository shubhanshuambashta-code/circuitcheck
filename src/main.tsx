import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import PagesPreview from './PagesPreview';
import './styles.css';
const Root=import.meta.env.MODE==='pages'?PagesPreview:App;
createRoot(document.getElementById('root')!).render(<React.StrictMode><Root/></React.StrictMode>);
