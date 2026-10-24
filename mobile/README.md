# SWALLOHear mobile (Expo)

The SWALLOHear app for Android and iOS, built with Expo SDK 58 and React Native. Research prototype, not a diagnostic device.

Full guide with screenshots: [`../docs/MOBILE_GUIDE.md`](../docs/MOBILE_GUIDE.md).

```bash
# 1. in the repo folder, with the project venv active
python api/server.py

# 2. here
npm install
npx expo start        # scan the QR code with Expo Go; press w for the web version
```

Checks: `npm run typecheck`, `npm run lint`, `npx expo-doctor`.
