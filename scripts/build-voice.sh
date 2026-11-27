#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ndk_toolchain="${ANDROID_HOME:-$HOME/android-sdk}/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$ndk_toolchain/aarch64-linux-android23-clang"
export CARGO_TARGET_X86_64_LINUX_ANDROID_LINKER="$ndk_toolchain/x86_64-linux-android23-clang"
export CARGO_TARGET_ARMV7_LINUX_ANDROIDEABI_LINKER="$ndk_toolchain/armv7a-linux-androideabi23-clang"
export CARGO_TARGET_I686_LINUX_ANDROID_LINKER="$ndk_toolchain/i686-linux-android23-clang"
for target in aarch64-linux-android x86_64-linux-android armv7-linux-androideabi i686-linux-android; do
    cargo build --offline --manifest-path voice-core/Cargo.toml --release --target "$target"
done
mkdir -p android/app/src/main/jniLibs/{arm64-v8a,x86_64,armeabi-v7a,x86}
cp voice-core/target/aarch64-linux-android/release/libodysseus_voice.so android/app/src/main/jniLibs/arm64-v8a/
cp voice-core/target/x86_64-linux-android/release/libodysseus_voice.so android/app/src/main/jniLibs/x86_64/
cp voice-core/target/armv7-linux-androideabi/release/libodysseus_voice.so android/app/src/main/jniLibs/armeabi-v7a/
cp voice-core/target/i686-linux-android/release/libodysseus_voice.so android/app/src/main/jniLibs/x86/
