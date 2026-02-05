#!/usr/bin/env bash
set -e

# At top of script, after set -e
BUILD_ENGINE=true
BUILD_SHADERS=true
BUILD_CONTENT=true

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-engine)   BUILD_ENGINE=false; shift ;;
    --no-shaders)  BUILD_SHADERS=false; shift ;;
    --no-content)  BUILD_CONTENT=false; shift ;;
    --only-engine) BUILD_SHADERS=false; BUILD_CONTENT=false; shift ;;
    --help|-h)
      echo "Usage: sbox-build [--no-engine] [--no-shaders] [--no-content] [--only-engine]"
      echo "Env vars: SBOX_CONFIG, SBOX_JOBS, BUILD_ENGINE/ SHADERS/CONTENT (true/false)"
      exit 0
      ;;
    *) echo "Unknown option $1"; exit 1 ;;
  esac
done

CONFIG="${SBOX_CONFIG:-Developer}"
JOBS="${SBOX_JOBS:-$(nproc)}"
DOTNET="C:\\Program Files\\dotnet\\dotnet.exe"

# New toggles - set these as env vars when running the container, e.g. -e BUILD_ENGINE=false
BUILD_ENGINE="${BUILD_ENGINE:-true}"
BUILD_SHADERS="${BUILD_SHADERS:-true}"
BUILD_CONTENT="${BUILD_CONTENT:-true}"

export PATH="$PATH:C:\\MinGW\\bin"

echo "==> s&box build ($CONFIG) using $JOBS jobs"
echo "    Engine:  $BUILD_ENGINE"
echo "    Shaders: $BUILD_SHADERS"
echo "    Content: $BUILD_CONTENT"

# Build engine (core step - usually always needed)
if [ "$BUILD_ENGINE" = "true" ]; then
  echo "==> Building engine..."
  xvfb-run -a wine "$DOTNET" run \
    --project ./engine/Tools/SboxBuild/SboxBuild.csproj \
    -- build --config "$CONFIG"
else
  echo "==> Skipping engine build"
fi

# Build shaders in parallel if enabled
if [ "$BUILD_SHADERS" = "true" ]; then
  xvfb-run -a wine "$DOTNET" run \
    --project ./engine/Tools/SboxBuild/SboxBuild.csproj \
    -- build-shaders &
  PID_SHADERS=$!
else
  echo "==> Skipping shaders"
  PID_SHADERS=""
fi

# Build content in parallel if enabled
if [ "$BUILD_CONTENT" = "true" ]; then
  xvfb-run -a wine "$DOTNET" run \
    --project ./engine/Tools/SboxBuild/SboxBuild.csproj \
    -- build-content &
  PID_CONTENT=$!
else
  echo "==> Skipping content"
  PID_CONTENT=""
fi

# Wait for any background jobs that were started
if [ -n "$PID_SHADERS" ]; then
  wait $PID_SHADERS || { echo "Shaders failed"; exit 1; }
fi
if [ -n "$PID_CONTENT" ]; then
  wait $PID_CONTENT || { echo "Content failed"; exit 1; }
fi

echo "==> Build complete"
