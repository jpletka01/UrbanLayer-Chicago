import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import 'mapbox-gl/dist/mapbox-gl.css'
import './index.css'
import { App } from './App.tsx'
import { AboutPage } from './components/AboutPage.tsx'
import { AdminDashboard } from './components/AdminDashboard.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/c/:id" element={<App />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
