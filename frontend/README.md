# Lyo Frontend

This folder contains the monolithic React UI for Lyo. It is built using Vite and Material UI for a modern look and feel. The project is organized so additional features can be added without splitting into micro-frontends.

There is also a separate `mobile/` folder that houses the Expo React Native application for iOS and Android.

## Development

1. Install dependencies
   ```bash
   npm install
   ```

2. Start the development server (proxying API requests to the backend)
   ```bash
   npm run dev
   ```

The dev server will be available at `http://localhost:5173` and API calls to `/api` will be forwarded to `http://localhost:8000`.
