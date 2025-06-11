import React from 'react';
import { ScrollView, Image, View, StyleSheet } from 'react-native';

const stories = new Array(10).fill(null);

export default function StoryCarousel() {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.container}>
      {stories.map((_, i) => (
        <View key={i} style={styles.story}>
          <Image source={{ uri: 'https://placekitten.com/200/200' }} style={styles.image} />
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 10,
  },
  story: {
    width: 70,
    height: 70,
    borderRadius: 35,
    overflow: 'hidden',
    marginHorizontal: 5,
  },
  image: {
    width: '100%',
    height: '100%',
  },
});
