import { useState } from 'react'
import { TextField, Button, Typography, Box } from '@mui/material'

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!res.ok) throw new Error('Login failed')
      const data = await res.json()
      localStorage.setItem('token', data.access_token)
      onLogin()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Box className="auth-container">
      <Typography variant="h5" mb={2}>Login</Typography>
      <form onSubmit={handleSubmit}>
        <TextField
          label="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        />
        <Button type="submit" variant="contained">Login</Button>
      </form>
      {error && <Typography color="error">{error}</Typography>}
    </Box>
  )
}
