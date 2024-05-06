use std::io;

use snafu::prelude::*;

use ddcache_rpc::rpc_capnp::error;
use ddcache_rpc::Endpoint;

#[derive(Debug, Snafu)]
#[snafu(visibility(pub(crate)))]
pub enum Error {
    #[snafu(display("client task stopped"))]
    Stopped,

    //
    // Shard errors.
    //
    #[snafu(display("connect error: {source}"))]
    Connect { source: io::Error },
    #[snafu(display("disconnected: {endpoint}"))]
    Disconnected { endpoint: Endpoint },
    #[snafu(display("not connected to any shard"))]
    NotConnected,
    #[snafu(display("request timeout"))]
    RequestTimeout,

    //
    // Decode response errors.
    //
    #[snafu(display("decode error: {source}"))]
    Decode { source: capnp::Error },
    #[snafu(display("unexpected response"))]
    UnexpectedResponse,

    //
    // Protocol errors.
    //
    #[snafu(display("server error"))]
    Server,
    #[snafu(display("shard unavailable"))]
    Unavailable,

    #[snafu(display("invalid request"))]
    InvalidRequest,
    #[snafu(display("expect key size <= {max}"))]
    MaxKeySizeExceeded { max: u32 },
    #[snafu(display("expect metadata size <= {max}"))]
    MaxMetadataSizeExceeded { max: u32 },
    #[snafu(display("expect blob size <= {max}"))]
    MaxBlobSizeExceeded { max: u32 },

    //
    // Blob I/O error.
    //
    #[snafu(display("blob request timeout"))]
    BlobRequestTimeout,
    #[snafu(display("blob io error: {source}"))]
    Io { source: io::Error },
    #[snafu(display("expect read/write {expect} bytes: {size}"))]
    PartialIo { size: usize, expect: usize },
}

impl TryFrom<error::Reader<'_>> for Error {
    type Error = capnp::Error;

    fn try_from(error: error::Reader<'_>) -> Result<Self, Self::Error> {
        Ok(match error.which()? {
            error::Server(()) => Error::Server,
            error::Unavailable(()) => Error::Unavailable,
            error::InvalidRequest(()) => Error::InvalidRequest,
            error::MaxKeySizeExceeded(max) => Error::MaxKeySizeExceeded { max },
            error::MaxMetadataSizeExceeded(max) => Error::MaxMetadataSizeExceeded { max },
            error::MaxBlobSizeExceeded(max) => Error::MaxBlobSizeExceeded { max },
        })
    }
}
