# syntax=docker/dockerfile:1

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# https://github.com/react-native-community/docker-android
# Pick a tag whose Android build tools match what Expo's version catalog
# generates in android/build.gradle so the container doesn't re-download them.
FROM reactnativecommunity/react-native-android:v20.1 AS builder

WORKDIR /reactnativesrc/
COPY . .

RUN npm install
# Regenerate the android/ project from app.json using Expo's continuous native
# generation. `--no-install` skips a redundant `npm install` since we just ran it.
RUN npx expo prebuild --platform android --no-install
WORKDIR android/
RUN chmod +x gradlew
RUN ./gradlew assembleRelease

FROM scratch
COPY --from=builder /reactnativesrc/android/app/build/outputs/apk/release/app-release.apk /reactnativeapp.apk
ENTRYPOINT ["/reactnativeapp.apk"]
