pub mod bigraph;
#[cfg(feature = "collections_ext")]
pub mod cursor_set;
#[cfg(feature = "collections_ext")]
pub mod index_map;
pub mod vec_list;

#[cfg(feature = "collections_ext")]
mod bimap;
mod table;

use std::iter::FusedIterator;

#[cfg(feature = "collections_ext")]
pub use self::bigraph::HashBiGraph;
pub use self::bigraph::{NaiveBTreeBiGraph, NaiveHashBiGraph};
#[cfg(feature = "collections_ext")]
pub use self::bimap::HashBiMap;
#[cfg(feature = "collections_ext")]
pub use self::cursor_set::HashCursorSet;
#[cfg(feature = "collections_ext")]
pub use self::index_map::HashIndexMap;
pub use self::table::HashBasedTable;
pub use self::vec_list::VecList;

// Default to stdlib's default hash builder, not hashbrown's.
#[cfg(feature = "collections_ext")]
pub type DefaultHashBuilder = std::collections::hash_map::RandomState;

// Generally, an iterator should implement these traits.
pub trait Iter<Item> =
    Clone + Iterator<Item = Item> + DoubleEndedIterator + ExactSizeIterator + FusedIterator;
pub trait IterMut<Item> =
    Iterator<Item = Item> + DoubleEndedIterator + ExactSizeIterator + FusedIterator;
