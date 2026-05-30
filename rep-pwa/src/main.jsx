import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(<App />);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('install-banner')?.classList.add('show');
});

document.getElementById('install-btn')?.addEventListener('click', async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  document.getElementById('install-banner')?.classList.remove('show');
});

document.getElementById('install-dismiss')?.addEventListener('click', () => {
  document.getElementById('install-banner')?.classList.remove('show');
});
