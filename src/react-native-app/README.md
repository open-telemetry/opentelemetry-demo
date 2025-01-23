# Example React Native app

This was created using
[`npx create-expo-app@latest`](https://reactnative.dev/docs/environment-setup#start-a-new-react-native-project-with-expo)

Content was taken from the web app example in src/frontend and modified to work
in a React Native environment.

## Get started

Start the OpenTelemetry demo from the root of this repo:

```bash
cd ../..
make start # or start-minimal
```

## Building the app

Unlike the other components under src/ which run within containers this
app must be built and then run on a mobile simulator on your machine or a
physical device. If this is your first time running a React Native app then in
order to execute the steps under "Build on your host machine" you will need to
setup your local environment for Android or iOS development or both following
[this guide](https://reactnative.dev/docs/set-up-your-environment).
Alternatively for Android you can instead follow the steps under "Build within a
container" to leverage a container to build the app's apk for you.

### Build on your host machine

Before building the app you will need to install the dependencies for the app.

```bash
cd src/react-native-app
npm install
```

#### Android: Build and run app

To run on Android, the following command will compile the Android app and deploy
it to a running Android simulator or connected device. It will also start a
a server to provide the JS Bundle required by the app.

```bash
npm run android
```

#### iOS: Setup dependencies

Before building for iOS you will need to setup the iOS dependency management
using CocoaPods. This command only needs to be run the first time before
building the app for iOS.

```bash
cd ios && pod install && cd ..
```

#### iOS: Build and run with XCode

To run on iOS you may find it cleanest to build through the XCode IDE. In order
to start a server to provide the JS Bundle, run the following command (feel free
to ignore the output commands referring to opening an iOS simulator, we'll do
that directly through XCode in the next step).

```bash
npm run start
```

Then open XCode, open this as an existing project by opening
`src/react-native-app/ios/react-native-app.xcworkspace` then trigger the build
by hitting the Play button or from the menu using Product->Run.

#### iOS: Build and run from the command-line

You can build and run the app using the command line with the following
command. This will compile the iOS app and deploy it to a running iOS simulator
and start a server to provide the JS Bundle.

```bash
npm run ios
```

### Build within a container

For Android builds you can produce an apk using Docker without requiring the dev
tools to be installed on your host. From this repository root run the
following command.

```bash
make build-react-native-android
```

Or directly from this folder using.

```bash
docker build -f android.Dockerfile --platform=linux/amd64 --output=. .
```

This will create a `react-native-app.apk` file in the directory where you ran
the command. If you have an Android emulator running on your machine then you
can drag and drop this file onto the emulator's window in order to install it.

## Troubleshooting

### JS Bundle: build issues

Try removing the `src/react-native-app/node_modules/` folder and then re-run
`npm install` from inside `src/react-native-app`.

### Android: build app issues

Try stopping and cleaning local services (in case there are unknown issues
related to the start of the app).

```bash
cd src/react-native-app/android
./gradlew --stop  // stop daemons
rm -rf ~/.gradle/caches/
```

### iOS: pod install issues

Note that the above is the quickest way to get going but you may end up with
slightly different versions of the Pods than what has been committed to this
repository, in order to install the precise versions first setup
[rbenv](https://github.com/rbenv/rbenv#installation) followed by the following
commands.

```bash
rbenv install 2.7.6 # the version of ruby we've pinned for this app
bundle install
cd ios
bundle exec pod install
```

### iOS: build app issues

If you see a build failure related to pods try forcing a clean install with and
then attempt another build after:

```bash
  cd src/react-native-app/ios
  rm Podfile.lock
  pod cache clean --all
  pod repo update --verbose
  pod deintegrate
  pod install --repo-update --verbose
```

If there is an error compiling or running the app try closing any open
simulators and clearing all derived data:

```bash
rm -rf ~/Library/Developer/Xcode/DerivedData
```
