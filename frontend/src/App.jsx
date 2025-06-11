import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import Feed from './pages/Feed'
import './App.css'

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!localStorage.getItem('token'))

  function handleLogin() {
    setAuthenticated(true)
  }

  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={authenticated ? <Feed /> : <Navigate to="/login" />} />
          <Route path="/login" element={<Login onLogin={handleLogin} />} />
          <Route path="/register" element={<Register onRegister={() => {}} />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
