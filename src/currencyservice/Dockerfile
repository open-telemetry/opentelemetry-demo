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

# The following arguments would be passed from docker-compose.yml
ARG GRPC_VERSION
ARG OPENTELEMETRY_VERSION

# Install GRPC
RUN git clone --shallow-submodules --depth 1 --recurse-submodules -b v${GRPC_VERSION} \
  https://github.com/grpc/grpc \
  && cd grpc \
  && mkdir -p cmake/build \
  && cd cmake/build \
  && cmake \
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
  && make -j2 \
  && make install \
  && cd ../../.. \
  && rm -rf grpc

# install opentelemetry
RUN git clone https://github.com/open-telemetry/opentelemetry-cpp \
    && cd opentelemetry-cpp/ \
    && git checkout tags/v${OPENTELEMETRY_VERSION} -b v${OPENTELEMETRY_VERSION} \
    && git submodule update --init --recursive \
    && mkdir build \
    && cd build \
    && cmake .. -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DWITH_OTLP=ON \
    && make -j install && cd ../.. && rm -rf opentelemetry-cpp

COPY . /currencyservice

RUN cd /currencyservice \
    && mkdir -p build && cd build \
    && cmake .. && make -j install

ENTRYPOINT /usr/local/bin/currencyservice ${CURRENCY_SERVICE_PORT}
