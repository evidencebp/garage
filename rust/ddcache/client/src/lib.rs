#![feature(try_blocks)]

mod blob;
mod client;
mod error;
mod route;
mod shard;

use std::time::Duration;

pub use ddcache_rpc::{BlobMetadata, Timestamp};

pub use crate::client::{Client, ClientGuard};
pub use crate::error::Error;

g1_param::define!(request_timeout: Duration = Duration::from_secs(2));
g1_param::define!(blob_request_timeout: Duration = Duration::from_secs(8));
