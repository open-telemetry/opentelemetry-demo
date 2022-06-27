fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("proto/demo.proto")?;
    tonic_build::compile_protos("proto/grpc/health/v1/health.proto")?;
    Ok(())
}