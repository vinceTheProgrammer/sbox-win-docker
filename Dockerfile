FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEPREFIX=/root/.wine64
ENV WINEARCH=win64
ENV DISPLAY=:0
ENV WINEDEBUG=-all
ENV HOME=/root
ENV TEMP=C:\\windows\\temp
ENV TMP=C:\\windows\\temp

# Pin winetricks to a specific commit for reproducible builds
ARG WINETRICKS_COMMIT=b76e1ee79ac57d7aceb384f74518fc423265810c

RUN dpkg --add-architecture i386

RUN apt-get update -qq && \
    apt-get install -qq \
        curl wget git xvfb winbind \
        wine64 wine32:i386 \
        cabextract bzip2 ca-certificates \
        cmake ninja-build mingw-w64 \
        p7zip-full unzip && \
    rm -rf /var/lib/apt/lists/*

# Initialize Wine
RUN xvfb-run -a wineboot --init && \
    wineserver -w

# Fix NuGet cache folder (prevents restore errors)
RUN mkdir -p /root/.wine64/drive_c/users/root/.nuget

# Install Winetricks
RUN wget -q \
      https://raw.githubusercontent.com/Winetricks/winetricks/${WINETRICKS_COMMIT}/src/winetricks && \
    chmod +x winetricks && \
    mv winetricks /usr/bin/

# Install .NET SDK
RUN wget -q https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.102/dotnet-sdk-10.0.102-win-x64.exe && \
    xvfb-run -a wine dotnet-sdk-10.0.102-win-x64.exe /install /quiet && \
    rm dotnet-sdk-10.0.102-win-x64.exe

# Install trusted root cert
RUN wget --no-check-certificate -q https://symantec.tbs-certificats.com/vsign-universal-root.crt && \
    mkdir -p /usr/local/share/ca-certificates/extra && \
    cp vsign-universal-root.crt /usr/local/share/ca-certificates/extra/ && \
    update-ca-certificates && \
    rm vsign-universal-root.crt

# Winetricks for DirectX, DXVK, etc.
RUN xvfb-run -a winetricks -q \
    d3dxof dxdiag dxvk dxvk_async dxvk_nvapi \
    || echo "winetricks failed, continuing..."

RUN rm -rf /root/.cache/winetricks

# Create MinGW/bin directory (still used for symlink or custom tools if needed)
RUN mkdir -p /root/.wine64/drive_c/MinGW/bin

# Install Git for Windows inside Wine - extract to standard-ish location
RUN wget -q https://github.com/git-for-windows/git/releases/download/v2.52.0.windows.1/Git-2.52.0-64-bit.tar.bz2 && \
    mkdir -p /root/.wine64/drive_c/Git && \
    tar xjf Git-2.52.0-64-bit.tar.bz2 -C /root/.wine64/drive_c/Git && \
    rm Git-2.52.0-64-bit.tar.bz2 && \
    # Optional: symlink git.exe into MinGW/bin if some scripts expect it there
    ln -s /root/.wine64/drive_c/Git/bin/git.exe /root/.wine64/drive_c/MinGW/bin/git.exe

# Add Git, MinGW, and dotnet to Windows PATH via registry
# Explicitly include dotnet.exe path to avoid Wine extension/PATH search quirks
RUN xvfb-run -a wine reg add "HKLM\\System\\CurrentControlSet\\Control\\Session Manager\\Environment" \
    /v Path \
    /t REG_EXPAND_SZ \
    /d "C:\\Git\\cmd;C:\\Git\\usr\\bin;C:\\Git\\bin;C:\\MinGW\\bin;C:\\Program Files\\dotnet;%SystemRoot%\\system32;%SystemRoot%;%SystemRoot%\\System32\\Wbem" \
    /f && \
    # Also add as USER env (sometimes child processes inherit better from HKCU)
    xvfb-run -a wine reg add "HKCU\\Environment" \
    /v Path \
    /t REG_EXPAND_SZ \
    /d "C:\\Git\\cmd;C:\\Git\\usr\\bin;C:\\Git\\bin;C:\\MinGW\\bin;C:\\Program Files\\dotnet;%SystemRoot%\\system32;%SystemRoot%;%SystemRoot%\\System32\\Wbem" \
    /f && \
    wineserver -k && \
    wineserver -w

# Trust the s&box repo dir in Wine (prevents dubious ownership error)
# Use Z:/root/sbox since that's how Wine sees the WORKDIR mount
RUN xvfb-run -a wine cmd /c "git config --global --add safe.directory Z:/root/sbox" && \
    wineserver -k && \
    wineserver -w

# Trust repo for native Linux git
RUN git config --global --add safe.directory /root/sbox

# Add experimental smart build script
RUN apt-get update -qq && apt-get install -qq python3 && rm -rf /var/lib/apt/lists/*
COPY build.py /usr/local/bin/build
RUN chmod +x /usr/local/bin/build

WORKDIR /root/sbox

ENTRYPOINT ["build"]