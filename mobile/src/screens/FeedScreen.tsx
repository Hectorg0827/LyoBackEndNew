import React, { useEffect, useState } from 'react';
import { View, FlatList, Image, Text, StyleSheet } from 'react-native';
import StoryCarousel from '../components/StoryCarousel';

interface Post {
  id: number;
  text: string;
  media_url?: string;
}

export default function FeedScreen() {
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    const url = `${process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/feed`;
    fetch(url)
      .then(res => res.json())
      .then(data => setPosts(data.posts || []))
      .catch(() => {});
  }, []);

  return (
    <View style={styles.container}>
      <StoryCarousel />
      <FlatList
        data={posts}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => (
          <View style={styles.post}>
            {item.media_url && (
              <Image source={{ uri: item.media_url }} style={styles.image} />
            )}
            <Text>{item.text}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  post: {
    marginBottom: 16,
  },
  image: {
    width: '100%',
    aspectRatio: 1,
  },
});
