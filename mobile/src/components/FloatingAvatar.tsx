import React from 'react';
import { StyleSheet, Pressable, View, Text } from 'react-native';

export default function FloatingAvatar({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.container} onPress={onPress}>
      <View style={styles.avatar}>
        <Text style={styles.label}>AI</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 20,
    right: 20,
  },
  avatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#6200ee',
    justifyContent: 'center',
    alignItems: 'center',
  },
  label: {
    color: 'white',
    fontWeight: 'bold',
  },
});
