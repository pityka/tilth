/// Any null byte in the first 512 bytes → binary.
/// Uses memchr for the scan — single SIMD pass, no branching.
pub fn is_binary(buf: &[u8]) -> bool {
    let window = &buf[..buf.len().min(512)];
    memchr::memchr(0, window).is_some()
}
