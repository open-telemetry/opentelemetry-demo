# Example React Native app

This was created using [`npx create-expo-app@latest`](https://reactnative.dev/docs/environment-setup#start-a-new-react-native-project-with-expo)

Content was taken from the web app example in src/frontend and modified to work
in a React Native environment.

## Get started

Start the OpenTelemetry demo:

```bash
cd ../..
make start # or start-minimal
```

## Building the app

Unlike the other components under src/ which run within docker containers this
app must be built and then run on a mobile simulator on your machine or a physical
device. If this is your first time running a React Native app then in order to
execute the steps under "Build on your host machine" you will need to setup your
local environment for Android or iOS development or both following
[this guide](https://reactnative.dev/docs/set-up-your-environment). Alternatively
for Android you can instead follow the steps under "Build within a container" to
leverage a container to build the app's apk for you.

### Build on your host machine

Build and run the React Native app for a given platform by running these make targets
from the project root:

```bash
make reactnative-run-android
```

Or

```bash
make reactnative-run-ios
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

Note that for all the above commands a release build is created rather than a debug
one to avoid needing a dev server to provide the JS bundle.

### Build within a container

For Android builds you can produce an apk using Docker without requiring the dev
tools to be installed on your host. From the project root run:

```bash
make reactnative-build-android
```

Or directly from this folder using:

```bash
docker build -f android.Dockerfile --output=. .
```

This will produce `reactnativeapp.apk` in the directory where you ran the command.
If you have an Android emulator running on your machine then you can simply drag
and drop this file onto the emulator's window in order to install it.

TODO: For a physical device you can install this by sending the apk file to your
device, giving the "Install unknown apps" permission to the app you will be opening
the file with, and then installing it. However this won't be able to hit the APIs
because they are hard-coded to be localhost, need those to be configurable before
this method would work.
