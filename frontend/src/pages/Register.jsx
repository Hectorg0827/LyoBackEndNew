import { useState } from 'react'
import { TextField, Button, Typography, Box } from '@mui/material'

export default function Register({ onRegister }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, display_name: displayName })
      })
      if (!res.ok) throw new Error('Registration failed')
      onRegister()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Box className="auth-container">
      <Typography variant="h5" mb={2}>Register</Typography>
      <form onSubmit={handleSubmit}>
        <TextField
          label="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        />
        <TextField
          label="Display Name"
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
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
        <Button type="submit" variant="contained">Register</Button>
      </form>
      {error && <Typography color="error">{error}</Typography>}
    </Box>
  )
}
