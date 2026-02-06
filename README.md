# sbox-win-docker
`sbox-win-docker` provides a single script to run while inside of the `sbox-public` repo, which will build sbox for you. It uses docker under the hood, but you shouldn't need to worry about that.

## Installation
```
sudo curl -L https://raw.githubusercontent.com/vinceTheProgrammer/sbox-win-docker/refs/heads/main/sbox-build -o /usr/local/bin/sbox-build
sudo chmod +x /usr/local/bin/sbox-build
```

## Usage
While in any `sbox-public` repo:
```
sbox-build
```

Note: if Docker is not installed, started, or set up, `sbox-build` will walk you through it.

## Credit
- Used the Dockerfile created by tsktp as the foundation: https://github.com/tsktp/sbox-public-linux-docker
- DrakeFruit's fork of tsktp's repo was the inpiration for the build script https://github.com/DrakeFruit/sbox-public-linux-docker
- ChatGPT and Grok wrote much of the Dockerfile additions and build scripts, but I understand it 95% line for line, so blame ~~any~~95% of problems on me

## License
License is MIT, so do whatever with it