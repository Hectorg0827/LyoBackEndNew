import { AppBar, Toolbar, Typography, Button, Container } from '@mui/material'
import { Link } from 'react-router-dom'

export default function Layout({ children }) {
  return (
    <>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar sx={{ display: 'flex', gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }} component={Link} to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
            Lyo
          </Typography>
          <Button component={Link} to="/login" color="inherit">Login</Button>
          <Button component={Link} to="/register" color="inherit">Register</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ mt: 3 }}>
        {children}
      </Container>
    </>
  )
}
