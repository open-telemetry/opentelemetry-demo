# protos are loaded at build time for rust.
# to build the docker image properly, we must copy them over.
# Cargo / Rust is able to do this from the original host directory, but docker cannot reference outside the build ctx.

mkdir -p proto
cp -r ../../pb/* ./proto
