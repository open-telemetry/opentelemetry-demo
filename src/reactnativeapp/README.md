# Example React Native app

This was created using [`npx create-expo-app@latest`](https://reactnative.dev/docs/environment-setup#start-a-new-react-native-project-with-expo)

Content was taken from the web app example in src/frontend and modified to work
in a React Native environment.

## Get started

Unlike the other components under src/ which run within docker containers this
app is meant to be run on either mobile emulators on your machine or physical
devices. If this is your first time running a React Native app you will need to
setup your local environment for Android or iOS development or both following
[this guide](https://reactnative.dev/docs/set-up-your-environment).

Start the OpenTelemetry demo:

```bash
cd ../..
make start # or start-minimal
```

Then start the React Native app:

```bash
make reactnative-android
```

Or

```bash
make reactnative-ios
```

You can also install dependencies and launch the app directly from this folder using:

```bash
cd src/reactnativeapp
npm install
```

```bash
npm run android
```

Or

```bash
npm run ios
```
