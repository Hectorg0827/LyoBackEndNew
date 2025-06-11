import React from 'react';
import { View, Text, StyleSheet, Alert } from 'react-native';
import FloatingAvatar from '../components/FloatingAvatar';

export default function LearnScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Learn</Text>
      <FloatingAvatar onPress={() => Alert.alert('AI Avatar', 'Generate a course for the user')} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
  },
  heading: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 16,
  },
});
