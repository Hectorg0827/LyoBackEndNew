# Lyo Mobile

This folder contains the Expo React Native mobile application for Lyo. The mobile app is designed as a monolith so that additional features can be added without splitting into multiple projects.

## Development

1. Install the Expo CLI and project dependencies (requires Node 18+)
   ```bash
   npm install -g expo-cli
   npm install
   ```

2. Start the development server
   ```bash
   expo start
   ```

The app expects the backend API to be available at `http://localhost:8000` by default. You can override this by setting the `EXPO_PUBLIC_API_URL` environment variable.
