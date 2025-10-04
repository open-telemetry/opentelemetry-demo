cmake_minimum_required(VERSION 3.1)
project(currency)

find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)
find_package(opentelemetry-cpp CONFIG REQUIRED)

set(GENERATED_PROTOBUF_PATH "${CMAKE_BINARY_DIR}/generated/proto")

add_subdirectory(genproto)

include_directories("${GENERATED_PROTOBUF_PATH}" "${OPENTELEMETRY_CPP_INCLUDE_DIRS}")

add_executable(currency src/server.cpp)
add_dependencies(currency demo-proto)
target_link_libraries(
    currency demo-proto protobuf::libprotobuf
     ${OPENTELEMETRY_CPP_LIBRARIES} opentelemetry_trace opentelemetry_common 
     opentelemetry_exporter_otlp_grpc opentelemetry_exporter_otlp_grpc_client 
     opentelemetry_proto opentelemetry_otlp_recordable opentelemetry_resources 
     opentelemetry_metrics opentelemetry_exporter_otlp_grpc_metrics gRPC::grpc++)

install(TARGETS currency DESTINATION bin)
