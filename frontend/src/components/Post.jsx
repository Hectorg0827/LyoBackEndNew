import { Card, CardMedia, CardContent, Typography } from '@mui/material'

export default function Post({ post }) {
  return (
    <Card sx={{ mb: 2 }}>
      {post.media_url && (
        <CardMedia component="img" src={post.media_url} alt="media" />
      )}
      <CardContent>
        <Typography>{post.text}</Typography>
      </CardContent>
    </Card>
  )
}
