# sbox-win-docker
`sbox-win-docker` provides a single script to run while inside of the `sbox-public` repo, which will build sbox for you. It uses docker under the hood, but you shouldn't need to worry about that.

## First time setup

1. install Docker https://docs.docker.com/engine/install/
2. start Docker and make sure it's running:
```
sudo systemctl enable --now docker
systemctl status docker
```
3. create docker group:
```
sudo groupadd docker
```
4. add yourself to `docker` group (log out/in for it to take effect):
```
sudo usermod -aG docker $USER
```
5. clone repo and build Docker image
```
git clone https://github.com/vinceTheProgrammer/sbox-win-docker
cd sbox-win-docker
docker build -t sbox-win-docker .
chmod +x sbox-build
```
6. (optional) add `sbox-build` script onto your PATH so you can run it like a typical command from anywhere without having to type out the full path to it.
There are many ways to do it, but here's one:

copy script someplace designated for user executables:
```
mkdir -p ~/.local/bin
cp ./sbox-build ~/.local/bin/sbox-build
chmod +x ~/.local/bin/sbox-build
```
then make sure that place is on your PATH:
```
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Usage
1. cd into any `sbox-public` repo
2. execute the `sbox-build` script you made exectuable during first time setup

(`sbox-build --help` for build options)

## Credit
- Used the Dockerfile created by tsktp as the foundation: https://github.com/tsktp/sbox-public-linux-docker
- DrakeFruit's fork of tsktp's repo was the inpiration for the build script https://github.com/DrakeFruit/sbox-public-linux-docker
- ChatGPT and Grok wrote much of the Dockerfile additions and build scripts, but I understand it line for line, so blame any problems on me

## License
License is MIT, so do whatever with it