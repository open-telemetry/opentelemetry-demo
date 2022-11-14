FROM ubuntu:20.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -y update
RUN apt-get -y upgrade && apt-get -y dist-upgrade
RUN apt-get install -qq -y --ignore-missing \
  build-essential                           \
  git                                       \
  make                                      \
  pkg-config                                \
  protobuf-compiler                         \
  libprotobuf-dev                           \
  libcurl4-openssl-dev                      \
  nlohmann-json3-dev                        \
  cmake 
RUN apt-get install -qq -y gcc-10 g++-10 cpp-10
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 100 --slave /usr/bin/g++ g++ /usr/bin/g++-10 --slave /usr/bin/gcov gcov /usr/bin/gcov-10

# The following arguments would be passed from docker-compose.yml
ARG GRPC_VERSION=1.46.0
ARG OPENTELEMETRY_VERSION=1.5.0
ARG MOLD_VERSION=1.7.0

# Install mold
RUN git clone -b v${MOLD_VERSION} \
  https://github.com/rui314/mold.git \
  && mkdir mold/build \
  && cd mold/build \
  && ../install-build-deps.sh \
  && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-10 .. \
  && cmake --build . -j $(nproc) \
  && cmake --install .

# Install GRPC
RUN git clone --shallow-submodules --depth 1 --recurse-submodules -b v${GRPC_VERSION} \
  https://github.com/grpc/grpc \
  && cd grpc \
  && mkdir -p cmake/build \
  && cd cmake/build \
  && cmake \
    -DCMAKE_CXX_FLAGS="-B/usr/libexec/mold" \
    -DgRPC_INSTALL=ON \
    -DgRPC_BUILD_TESTS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DgRPC_BUILD_GRPC_NODE_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_OBJECTIVE_C_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_PHP_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_PHP_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_PYTHON_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_RUBY_PLUGIN=OFF \
    ../.. \
  && make -j$(nproc || sysctl -n hw.ncpu || echo 1) \
  && make install \
  && cd ../../.. \
  && rm -rf grpc

# Install OpenTelemetry
RUN git clone https://github.com/open-telemetry/opentelemetry-cpp \
    && cd opentelemetry-cpp/ \
    && git checkout tags/v${OPENTELEMETRY_VERSION} -b v${OPENTELEMETRY_VERSION} \
    && git submodule update --init --recursive \
    && mkdir build \
    && cd build \
    && cmake .. -DCMAKE_CXX_FLAGS="-B/usr/libexec/mold" -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DWITH_OTLP=ON \
    && make -j install && cd ../.. && rm -rf opentelemetry-cpp

COPY . /currencyservice

RUN cd /currencyservice \
    && mkdir -p build && cd build \
    && cmake .. && make -j install

ENTRYPOINT /usr/local/bin/currencyservice ${CURRENCY_SERVICE_PORT}
