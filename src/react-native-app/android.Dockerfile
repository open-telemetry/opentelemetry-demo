# syntax=docker/dockerfile:1

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# https://github.com/react-native-community/docker-android
# Choosing a tag where the Android build tools match what we have in android/build.gradle to avoid the
# container having to download them
FROM reactnativecommunity/react-native-android:v13.2.1 AS builder

WORKDIR /reactnativesrc/
COPY . .

RUN npm install
WORKDIR android/
RUN chmod +x gradlew
RUN ./gradlew assembleRelease

FROM scratch
COPY --from=builder /reactnativesrc/android/app/build/outputs/apk/release/app-release.apk /reactnativeapp.apk
ENTRYPOINT ["/reactnativeapp.apk"]
