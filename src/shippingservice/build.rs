fn main() -> Result<(), Box<dyn std::error::Error>> {
    #[cfg(feature = "dockerproto")]
    tonic_build::compile_protos("/app/proto/demo.proto")?;
    #[cfg(not(feature = "dockerproto"))]
    tonic_build::compile_protos("../../pb/demo.proto")?;
    Ok(())
}
