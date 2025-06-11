import { useEffect, useState } from 'react'
import Post from '../components/Post'
import { Box } from '@mui/material'

export default function Feed() {
  const [posts, setPosts] = useState([])

  useEffect(() => {
    async function load() {
      const token = localStorage.getItem('token')
      const res = await fetch('/api/v1/feed', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setPosts(data.posts || [])
      }
    }
    load()
  }, [])

  return (
    <Box className="feed">
      {posts.map(p => (
        <Post key={p.id} post={p} />
      ))}
    </Box>
  )
}
