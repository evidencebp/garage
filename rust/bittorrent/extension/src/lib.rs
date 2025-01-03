#![feature(iterator_try_collect)]

mod handshake;
mod metadata;
mod pex;

use std::convert::Infallible;

use bytes::Bytes;
use serde::de::Error as _;
use snafu::prelude::*;

use bittorrent_bencode::{convert, dict, own::Value, serde as serde_bencode};

//
// Implementer's Notes: Keep in mind that when decoding an extension message, use the extension ids
// from our handshake message.  When encoding an extension message, use the ids from the peer's
// handshake message.
//

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Enabled {
    pub metadata: bool,
    pub peer_exchange: bool,
}

impl Enabled {
    pub fn load() -> Self {
        Self::new(*metadata::enable(), *pex::enable())
    }

    pub fn new(metadata: bool, peer_exchange: bool) -> Self {
        Self {
            metadata,
            peer_exchange,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct Extension {
    name: &'static str,
    is_enabled: fn() -> bool,
    decode: fn(Bytes) -> Result<MessageOwner<Bytes>, serde_bencode::Error>,
}

// NOTE: The array index also serves as our extension id.
pub(crate) const EXTENSIONS: [Extension; NUM_EXTENSIONS] = [
    // BEP 10 Handshake
    Extension {
        name: "",
        is_enabled: || true,
        decode: |buffer| Ok(HandshakeOwner::try_from(buffer)?.try_into().unwrap()),
    },
    // BEP 9 Metadata
    Extension {
        name: "ut_metadata",
        is_enabled: || *metadata::enable(),
        decode: |buffer| Ok(MetadataOwner::try_from(buffer)?.try_into().unwrap()),
    },
    // BEP 11 Peer Exchange (PEX)
    Extension {
        name: "ut_pex",
        is_enabled: || *pex::enable(),
        decode: |buffer| Ok(PeerExchangeOwner::try_from(buffer)?.try_into().unwrap()),
    },
];

pub(crate) const NUM_EXTENSIONS: usize = 3;

pub fn decode(id: u8, buffer: Bytes) -> Result<MessageOwner<Bytes>, serde_bencode::Error> {
    fn get(id: u8) -> Result<&'static Extension, Error> {
        let extension = EXTENSIONS
            .get(usize::from(id))
            .context(UnknownExtensionIdSnafu { id })?;
        ensure!((extension.is_enabled)(), ExpectExtensionEnabledSnafu { id });
        Ok(extension)
    }

    let extension = get(id).map_err(serde_bencode::Error::custom)?;
    (extension.decode)(buffer)
}

/// Maps our extension ids to a peer's extension ids.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ExtensionIdMap {
    map: [u8; NUM_EXTENSIONS - 1],
}

impl ExtensionIdMap {
    pub fn new() -> Self {
        Default::default()
    }

    pub fn update(&mut self, peer_handshake: &Handshake) {
        for (id, extension) in EXTENSIONS.iter().enumerate() {
            if id != 0 {
                if let Some(peer_extension_id) = peer_handshake.extension_ids.get(extension.name) {
                    self.map[id - 1] = *peer_extension_id;
                }
            }
        }
    }

    pub fn peer_extensions(&self) -> Enabled {
        Enabled::new(
            self.get(Metadata::ID).is_some(),
            self.get(PeerExchange::ID).is_some(),
        )
    }

    pub fn map(&self, message: &Message) -> Option<u8> {
        self.get(message.id())
    }

    fn get(&self, id: u8) -> Option<u8> {
        if id == 0 {
            return Some(0);
        }
        let peer_extension_id = self.map[usize::from(id) - 1];
        (peer_extension_id != 0).then_some(peer_extension_id)
    }
}

//
// Message
//

g1_base::define_owner!(#[derive(Debug)] pub MessageOwner for Message);

g1_base::define_owner!(#[derive(Debug)] pub HandshakeOwner for Handshake);
g1_base::impl_owner_try_from!(HandshakeOwner for MessageOwner);

g1_base::define_owner!(#[derive(Debug)] pub MetadataOwner for Metadata);
g1_base::impl_owner_try_from!(MetadataOwner for MessageOwner);

g1_base::define_owner!(#[derive(Debug)] pub PeerExchangeOwner for PeerExchange);
g1_base::impl_owner_try_from!(PeerExchangeOwner for MessageOwner);

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Message<'a> {
    Handshake(Handshake<'a>),
    Metadata(Metadata<'a>),
    PeerExchange(PeerExchange<'a>),
}

pub use crate::handshake::Handshake;
pub use crate::metadata::{Data, Metadata, Reject, Request};
pub use crate::pex::{PeerContactInfo, PeerExchange, PeerFlag};

impl Message<'_> {
    pub(crate) fn id(&self) -> u8 {
        match self {
            Self::Handshake(_) => Handshake::ID,
            Self::Metadata(_) => Metadata::ID,
            Self::PeerExchange(_) => PeerExchange::ID,
        }
    }

    pub fn is_enabled(&self) -> bool {
        (EXTENSIONS[usize::from(self.id())].is_enabled)()
    }
}

// We implement a dummy `TryFrom` because `Message` cannot be decoded directly from a buffer (to
// decode the buffer, the extension id is also required, which conflicts with the trait requirement
// of `MessageOwner::try_from`).
//
// To obtain `MessageOwner`, the user decodes the buffer into a concrete message type (e.g.,
// `HandshakeOwner`) and then converts it into `MessageOwner`.
impl<'a> TryFrom<&'a [u8]> for Message<'a> {
    type Error = ();

    fn try_from(_: &'a [u8]) -> Result<Self, Self::Error> {
        std::unreachable!()
    }
}

// Unfortunately, some implementations do not adhere to BEP 3.  Let us try a lenient decoder; if it
// still does not work, return the original error.
macro_rules! decode_lenient {
    ($decode:path, $buffer:ident, $error:ident $(,)?) => {
        $decode($buffer)
            .inspect(|_| {
                tracing::debug!(
                    buffer = $buffer.escape_ascii().to_string(),
                    error = %$error,
                    "extension message strict decode error",
                );
            })
            .map_err(|_| $error)
    };
}

impl<'a> TryFrom<&'a [u8]> for Handshake<'a> {
    type Error = serde_bencode::Error;

    fn try_from(buffer: &'a [u8]) -> Result<Self, Self::Error> {
        serde_bencode::from_bytes(buffer).or_else(|error| {
            decode_lenient!(serde_bencode::from_bytes_lenient_two_pass, buffer, error)
        })
    }
}

impl<'a> TryFrom<Handshake<'a>> for Message<'a> {
    type Error = Infallible;

    fn try_from(handshake: Handshake<'a>) -> Result<Self, Self::Error> {
        Ok(Message::Handshake(handshake))
    }
}

impl<'a> TryFrom<&'a [u8]> for Metadata<'a> {
    type Error = serde_bencode::Error;

    fn try_from(buffer: &'a [u8]) -> Result<Self, Self::Error> {
        Self::decode(buffer).or_else(|error| decode_lenient!(Self::decode_lenient, buffer, error))
    }
}

impl<'a> TryFrom<Metadata<'a>> for Message<'a> {
    type Error = Infallible;

    fn try_from(metadata: Metadata<'a>) -> Result<Self, Self::Error> {
        Ok(Message::Metadata(metadata))
    }
}

impl<'a> TryFrom<&'a [u8]> for PeerExchange<'a> {
    type Error = serde_bencode::Error;

    fn try_from(buffer: &'a [u8]) -> Result<Self, Self::Error> {
        serde_bencode::from_bytes(buffer).or_else(|error| {
            decode_lenient!(serde_bencode::from_bytes_lenient_two_pass, buffer, error)
        })
    }
}

impl<'a> TryFrom<PeerExchange<'a>> for Message<'a> {
    type Error = Infallible;

    fn try_from(peer_exchange: PeerExchange<'a>) -> Result<Self, Self::Error> {
        Ok(Message::PeerExchange(peer_exchange))
    }
}

//
// Error
//

#[derive(Clone, Debug, Eq, PartialEq, Snafu)]
pub enum Error {
    #[snafu(display("expect byte string: {value:?}"))]
    ExpectByteString { value: Value },
    #[snafu(display("expect integer: {value:?}"))]
    ExpectInteger { value: Value },
    #[snafu(display("expect list: {value:?}"))]
    ExpectList { value: Value },
    #[snafu(display("expect dict: {value:?}"))]
    ExpectDictionary { value: Value },

    #[snafu(display("invalid utf8 string: \"{string}\""))]
    InvalidUtf8String { string: String },

    #[snafu(display("missing dictionary key: \"{key}\""))]
    MissingDictionaryKey { key: String },

    //
    // BEP 10
    //
    #[snafu(display("expect extension to be enabled: {id}"))]
    ExpectExtensionEnabled { id: u8 },
    #[snafu(display("invalid extension id: {id}"))]
    InvalidExtensionId { id: i64 },
    #[snafu(display("unknown extension id: {id}"))]
    UnknownExtensionId { id: u8 },

    //
    // BEP 9
    //
    #[snafu(display("invalid metadata piece: {piece}"))]
    InvalidMetadataPiece { piece: i64 },
    #[snafu(display("invalid metadata size: {size}"))]
    InvalidMetadataSize { size: i64 },
    #[snafu(display("unknown metadata message type: {message_type}"))]
    UnknownMetadataMessageType { message_type: i64 },

    //
    // BEP 11
    //
    #[snafu(display("expect peer exchange endpoints size == {expect}: {size}"))]
    ExpectPeerExchangeEndpointsSize { size: usize, expect: usize },
    #[snafu(display("invalid peer exchange endpoints: {endpoints:?}"))]
    InvalidPeerExchangeEndpoints { endpoints: Vec<u8> },
}

impl From<convert::Error> for Error {
    fn from(error: convert::Error) -> Self {
        match error {
            convert::Error::ExpectByteString { value } => Self::ExpectByteString { value },
            convert::Error::ExpectInteger { value } => Self::ExpectInteger { value },
            convert::Error::ExpectList { value } => Self::ExpectList { value },
            convert::Error::ExpectDictionary { value } => Self::ExpectDictionary { value },
            convert::Error::InvalidUtf8String { string } => Self::InvalidUtf8String { string },
        }
    }
}

impl From<dict::Error> for Error {
    fn from(error: dict::Error) -> Self {
        match error {
            dict::Error::MissingDictionaryKey { key } => Error::MissingDictionaryKey { key },
        }
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use super::*;

    #[test]
    fn update() {
        let mut map = ExtensionIdMap::new();
        assert_eq!(map, ExtensionIdMap { map: [0, 0] });

        map.update(&Handshake {
            extension_ids: BTreeMap::from([("foo", 42), ("ut_metadata", 99)]),
            metadata_size: None,
            extra: BTreeMap::from([]),
        });
        assert_eq!(map, ExtensionIdMap { map: [99, 0] });

        map.update(&Handshake {
            extension_ids: BTreeMap::from([("ut_metadata", 0), ("ut_pex", 100)]),
            metadata_size: None,
            extra: BTreeMap::from([]),
        });
        assert_eq!(map, ExtensionIdMap { map: [0, 100] });
    }

    #[test]
    fn get() {
        let mut map = ExtensionIdMap::new();
        assert_eq!(map.get(0), Some(0));
        assert_eq!(map.get(1), None);
        assert_eq!(map.get(2), None);

        map.update(&Handshake {
            extension_ids: BTreeMap::from([("ut_metadata", 99)]),
            metadata_size: None,
            extra: BTreeMap::from([]),
        });
        assert_eq!(map.get(0), Some(0));
        assert_eq!(map.get(1), Some(99));
        assert_eq!(map.get(2), None);

        map.update(&Handshake {
            extension_ids: BTreeMap::from([("ut_metadata", 0), ("ut_pex", 100)]),
            metadata_size: None,
            extra: BTreeMap::from([]),
        });
        assert_eq!(map.get(0), Some(0));
        assert_eq!(map.get(1), None);
        assert_eq!(map.get(2), Some(100));
    }
}
