fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("../../pb/demo.proto")?;
    tonic_build::compile_protos("../../pb/grpc/health/v1/health.proto")?;
    Ok(())
}