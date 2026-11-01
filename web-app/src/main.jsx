import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './style.css'
import { AuthProvider } from './context/AuthContext.jsx'

createRoot(document.getElementById('root')).render(<AuthProvider><App /></AuthProvider>)

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      console.error('PWA service worker registration failed:', error)
    })
  })
}
