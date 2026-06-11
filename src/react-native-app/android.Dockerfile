# syntax=docker/dockerfile:1

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# https://github.com/react-native-community/docker-android
# Pick a tag whose Android build tools match what Expo's version catalog
# generates in android/build.gradle so the container doesn't re-download them.
FROM reactnativecommunity/react-native-android:v20.1@sha256:88d93a9282e0f54f84cec7b979da6c5e3f20d87f5be246b75c231838be852fec AS builder

WORKDIR /reactnativesrc/
COPY . .

RUN npm ci
# Regenerate the android/ project from app.json using Expo's continuous native
# generation. `--no-install` skips a redundant install since dependencies are already present.
RUN npx expo prebuild --platform android --no-install
WORKDIR android/
RUN chmod +x gradlew
RUN ./gradlew assembleRelease

FROM scratch
COPY --from=builder /reactnativesrc/android/app/build/outputs/apk/release/app-release.apk /reactnativeapp.apk
ENTRYPOINT ["/reactnativeapp.apk"]
