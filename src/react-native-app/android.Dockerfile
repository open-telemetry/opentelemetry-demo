# syntax=docker/dockerfile:1

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# https://github.com/react-native-community/docker-android
# Pick a tag whose Android build tools match what Expo's version catalog
# generates in android/build.gradle so the container doesn't re-download them.
FROM reactnativecommunity/react-native-android:v21.0@sha256:24ca7ab5a70ec0b78a81bdc5eeea5924c2531531d53971b6f2321aff08446c36 AS builder

WORKDIR /reactnativesrc/
COPY . .

RUN npm ci
RUN npm run lint
# Regenerate the android/ project from app.json using Expo's continuous native
# generation. `--no-install` skips a redundant install since dependencies are already present.
RUN npx expo prebuild --platform android --no-install
WORKDIR android/
RUN chmod +x gradlew
RUN ./gradlew -Dorg.gradle.jvmargs="-Xmx2g -XX:MaxMetaspaceSize=1g" assembleRelease

FROM scratch
COPY --from=builder /reactnativesrc/android/app/build/outputs/apk/release/app-release.apk /reactnativeapp.apk
ENTRYPOINT ["/reactnativeapp.apk"]
