# Example React Native app

This was created using [`npx create-expo-app@latest`](https://reactnative.dev/docs/environment-setup#start-a-new-react-native-project-with-expo)

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
app must be built and then run on a mobile simulator on your machine or a physical
device. If this is your first time running a React Native app then in order to
execute the steps under "Build on your host machine" you will need to setup your
local environment for Android or iOS development or both following
[this guide](https://reactnative.dev/docs/set-up-your-environment). Alternatively
for Android you can instead follow the steps under "Build within a container" to
leverage a container to build the app's apk for you.

### Build on your host machine

Build and run the React Native app for a given platform by navigating to this folder
and running:

```bash
cd src/react-native-app
npm install
```

To run on Android:

```bash
npm run android
```

Note that for the above command a server is also spun up to serve the JS bundle
to the deployed app.

To run on iOS you may find it cleanest to build through the XCode IDE. First spin
up the react native dev server with the following (feel free to ignore the output
commands referring to opening an iOS simulator, we'll do that directly through
XCode in a later step):

```bash
npm run start
```

Then install the pods for the project:

```bash
cd ios
pod install
```

Note that the above is the quickest way to get going but you may end up with
slightly different versions of the Pods than what has been committed to this repo,
in order to install the precise versions first setup [rbenv](https://github.com/rbenv/rbenv#installation)
followed by:

```bash
rbenv install 2.7.6 # the version of ruby we've pinned for this app
bundle install
cd ios
bundle exec pod install
```

Then open XCode, open this as an existing project by opening `src/react-native-app/ios/react-native-app.xcworkspace`
then trigger the build by hitting the Play button or from the menu using Product->Run.

Or alternatively build and run from the command-line:

```bash
npm run ios
```

Note that for the above command a server is also spun up to serve the JS bundle
to the deployed apps.

### Build within a container

For Android builds you can produce an apk using Docker without requiring the dev
tools to be installed on your host. From the project root run:

```bash
make build-react-native-android
```

Or directly from this folder using:

```bash
docker build -f android.Dockerfile --platform=linux/amd64 --output=. .
```

This will produce `react-native-app.apk` in the directory where you ran the command.
If you have an Android emulator running on your machine then you can simply drag
and drop this file onto the emulator's window in order to install it following
[these steps](https://developer.android.com/studio/run/emulator-install-add-files).

TODO: For a physical device you can install this by sending the apk file to your
device, giving the "Install unknown apps" permission to the app you will be opening
the file with, and then installing it. However this won't be able to hit the APIs
because they are hard-coded to be localhost, need those to be configurable before
this method would work.

## Troubleshooting

### iOS build issues

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

If there is an error compiling or running the app try closing any open simulators
and clearing all derived data:

```bash
rm -rf ~/Library/Developer/Xcode/DerivedData
```

### Android build issues

Try stopping and cleaning local services (in case there are unknown issues related
to the start of the app):

```bash
  cd src/react-native-app/android
  ./gradlew --stop  // stop daemons
  rm -rf ~/.gradle/caches/
```

### JS build issues

Try removing the `src/react-native-app/node_modules/` folder and then re-run
`npm install` from inside `src/react-native-app`.
