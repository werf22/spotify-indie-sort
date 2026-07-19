
    use lazy_static::lazy_static;
    use rustc_hash::FxHashMap;
    use crate::spec::tag::ns::Namespace;

    pub struct AttributeMinification {
        pub boolean: bool,
        pub case_insensitive: bool,
        pub collapse: bool,
        pub default_value: Option<&'static [u8]>,
        pub redundant_if_empty: bool,
        pub trim: bool,
    }

    pub enum AttrMapEntry {
        AllNamespaceElements(AttributeMinification),
        SpecificNamespaceElements(FxHashMap<&'static [u8], AttributeMinification>),
    }

    pub struct ByNamespace {
        // Make pub so this struct can be statically created in gen/attrs.rs.
        pub html: Option<AttrMapEntry>,
        pub svg: Option<AttrMapEntry>,
    }

    impl ByNamespace {
        fn get(&self, ns: Namespace) -> Option<&AttrMapEntry> {
            match ns {
                Namespace::Html => self.html.as_ref(),
                Namespace::Svg => self.svg.as_ref(),
            }
        }
    }

    pub struct AttrMap(FxHashMap<&'static [u8], ByNamespace>);

    impl AttrMap {
        pub const fn new(map: FxHashMap<&'static [u8], ByNamespace>) -> AttrMap {
            AttrMap(map)
        }

        pub fn get(&self, ns: Namespace, tag: &[u8], attr: &[u8]) -> Option<&AttributeMinification> {
            self.0.get(attr).and_then(|namespaces| namespaces.get(ns)).and_then(|entry| match entry {
                AttrMapEntry::AllNamespaceElements(min) => Some(min),
                AttrMapEntry::SpecificNamespaceElements(map) => map.get(tag),
            })
        }
    }

    lazy_static! {
      pub static ref ATTRS: AttrMap = {
        #[allow(unused_mut)]
        let mut m = FxHashMap::<&'static [u8], ByNamespace>::default();
  m.insert(b"accumulate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"repeatcount", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"alignmentbaseline", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"playsinline", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"video", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"attributetype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"systemlanguage", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"elevation", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"end", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"dir", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"controlslist", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"d", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: true,
        default_value: None,
        redundant_if_empty: true,
        trim: true,
      }
    )),});m.insert(b"underlinethickness", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"in2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"overlineposition", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xmlspace", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"zoomandpan", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"enterkeyhint", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"vertadvy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"bias", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"preservealpha", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"paintorder", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"scrolling", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"defer", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"script", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"cellpadding", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"table", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"opacity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"action", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"vectoreffect", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"disableremoteplayback", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"video", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"allowfullscreen", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"start", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"ol", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"display", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"stroke", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"spellcheck", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"style", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: true,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: true,
      }
    )),});m.insert(b"fontstretch", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"mode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"loading", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"eager"),
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"eager"),
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"imagerendering", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"attributename", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"mediagroup", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"marginwidth", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"disablepictureinpicture", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"video", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"textrendering", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"divisor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"decelerate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"clippathunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"spreadmethod", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"type", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: true,
        collapse: false,
        default_value: Some(b"submit"),
        redundant_if_empty: false,
        trim: true,
      }
    );m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"menu", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"ol", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: true,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: true,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: true,
        collapse: false,
        default_value: Some(b"text"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"style", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"text/css"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"text/css"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"source", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"embed", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"rel", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"colorrendering", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"title", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"strokemiterlimit", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"targety", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"pointsatx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xmlbase", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"color", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"pointsatz", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"vocab", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"repeatdur", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"dirname", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"azimuth", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"accept", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"reversed", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"ol", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"security", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"content", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meta", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"ascent", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"stemh", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"k", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"unselectable", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"focusable", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"horizadvx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"arabicform", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"radius", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"rotate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fill", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"underlineposition", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"mask", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"by", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"horizoriginx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"default", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"track", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"nonce", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"style", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"charset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"meta", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"autocomplete", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"calcmode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"dx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"disabled", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"option", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"fieldset", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"optgroup", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"keygen", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"autosave", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"orient", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xlinktitle", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"scope", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"fontweight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"g2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"pointsaty", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"string", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"accesskey", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"prefix", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"formenctype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"application/x-www-form-urlencoded"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"application/x-www-form-urlencoded"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"direction", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"additive", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"u2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"values", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"filter", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"local", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"about", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"order", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"r", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"x2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"diffuseconstant", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"allow", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"unitsperem", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"markerend", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"translate", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"contenteditable", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"x1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"readonly", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"lengthadjust", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"stopcolor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"wrap", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"kerning", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"to", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"markerwidth", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"patternunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"visibility", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xlinkarcrole", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"floodcolor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"writingmode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"data", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"resource", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"property", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"autocapitalize", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"size", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"xchannelselector", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"primitiveunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"seamless", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"controls", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"baselineshift", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"colorinterpolation", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"edgemode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"formaction", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"htmlfor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"output", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"label", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"stitchtiles", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"enctype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"application/x-www-form-urlencoded"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"colspan", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"inputmode", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"span", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"colgroup", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"1"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"col", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"1"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"high", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"summary", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"table", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"rows", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"usemap", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"contentstyletype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"specularexponent", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"from", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"selected", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"option", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"fx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"list", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"href", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"base", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"panose1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"min", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"externalresourcesrequired", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"lang", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"slot", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"preserveaspectratio", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"value", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"progress", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"param", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"li", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"data", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"option", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"startoffset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"keypoints", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"pointerevents", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"itemid", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"itemprop", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"preload", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"checked", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"maskcontentunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"cy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"srcdoc", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"seed", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"alt", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"slope", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"cx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"glyphref", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fontvariant", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"maskunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"enablebackground", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"datetime", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"ins", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"time", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"del", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"overlinethickness", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"patterntransform", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"cursor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"points", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"spacing", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"viewbox", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"bbox", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"multiple", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"select", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"clippath", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"shaperendering", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"itemscope", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"srcset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"source", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"tablevalues", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xlinkrole", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"low", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"y1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"scale", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"challenge", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"keygen", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"fontsizeadjust", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"descent", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"u1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"id", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"muted", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"floodopacity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"gradienttransform", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"colorprofile", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"baseprofile", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fillrule", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"k1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"mathematical", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"strokedashoffset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"width", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"canvas", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"video", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"table", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"300"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"embed", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"col", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"results", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"renderingintent", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xlinktype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"is", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"sizes", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"source", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"patterncontentunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"exponent", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"hidden", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"placeholder", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"autofocus", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"keygen", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"sandbox", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"decoding", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"auto"),
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"manifest", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"html", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"async", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"script", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"dy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"autoplay", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"as", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"basefrequency", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"marginheight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"ideographic", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"markerheight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"itemtype", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"markerstart", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"orientation", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"textanchor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"k2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"unicoderange", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xheight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"dur", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"valign", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"refx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"crossorigin", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"accentheight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"target", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"base", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"_self"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"_self"),
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"formnovalidate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"frameborder", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"1"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"minlength", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"refy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"glyphorientationhorizontal", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"download", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"integrity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"ry", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"specularconstant", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"strikethroughposition", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"typeof", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"pattern", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"strokedasharray", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"step", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"stemv", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"referrerpolicy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"no-referrer-when-downgrade"),
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"no-referrer-when-downgrade"),
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"vertoriginx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"ychannelselector", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"contentscripttype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"amplitude", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"g1", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"poster", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"video", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"coords", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"onchange", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"acceptcharset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"scoped", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"style", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"allowreorder", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"k3", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"markerunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"allowtransparency", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"iframe", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"textdecoration", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"transform", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"y", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"lightingcolor", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"hanging", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xlinkhref", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"wmode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"keytimes", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"letterspacing", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"vmathematical", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xmlnsxlink", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"role", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"stddeviation", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"rowspan", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"inlist", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"nomodule", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"script", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"glyphname", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"keytype", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"keygen", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"contextmenu", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"name", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"map", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"fieldset", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"slot", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"keygen", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"param", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"output", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"meta", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"novalidate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"form", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"numoctaves", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"offset", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"restart", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"valphabetic", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"capture", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"fillopacity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"filterunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"origin", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"overflow", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"y2", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"widths", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"autocorrect", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"cellspacing", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"table", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"xlinkactuate", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"kernelunitlength", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"z", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"path", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"format", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"k4", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"markermid", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"datatype", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"srclang", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"track", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"kind", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"track", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"autoreverse", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"fontsize", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"x", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"vhanging", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"radiogroup", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"alphabetic", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"keysplines", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"limitingconeangle", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"strokelinecap", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"strokewidth", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"requiredfeatures", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"textlength", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"cliprule", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"form", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"fieldset", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"keygen", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"label", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"output", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"itemref", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"intercept", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"src", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"track", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"embed", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"script", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"source", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"hreflang", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"open", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"details", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"dialog", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"maxlength", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"rx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"class", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: true,
        default_value: None,
        redundant_if_empty: true,
        trim: true,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"vertoriginy", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"abbr", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"httpequiv", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meta", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"tabindex", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xmlns", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"align", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"method", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"form", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"get"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"keyparams", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"keygen", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"classid", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"headers", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"th", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"max", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"progress", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"strokelinejoin", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"dominantbaseline", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"wordspacing", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"ping", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"clip", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"cols", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"textarea", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"shape", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"rect"),
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"cite", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"blockquote", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"ins", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"quote", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"del", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"draggable", ByNamespace {html:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"loop", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"media", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"optimum", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"meter", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"glyphorientationvertical", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"gradientunits", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"in", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"operator", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"colorinterpolationfilters", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    )),});m.insert(b"strokeopacity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fontstyle", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"capheight", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"filterres", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"requiredextensions", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"viewtarget", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"height", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"td", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"iframe", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"150"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"embed", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"img", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"canvas", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"object", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"video", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"formtarget", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"label", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"option", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"optgroup", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"track", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"stopopacity", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"strikethroughthickness", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"formmethod", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"button", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"input", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"xlinkshow", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"xmllang", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"surfacescale", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"unicode", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"pathlength", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"speed", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"videographic", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"version", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"media", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"style", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: Some(b"all"),
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"meta", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"link", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"a", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"area", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );m.insert(b"source", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"fontfamily", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"required", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"input", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"textarea", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );m.insert(b"select", 
      AttributeMinification {
        boolean: true,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"targetx", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"result", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"begin", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"kernelmatrix", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});m.insert(b"ontoggle", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                m.insert(b"details", 
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: false,
        trim: false,
      }
    );
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,});m.insert(b"unicodebidi", ByNamespace {html:
                  Some({
                    #[allow(unused_mut)]
                    let mut m = FxHashMap::<&'static [u8], AttributeMinification>::default();
                
                  AttrMapEntry::SpecificNamespaceElements(m)
                })
              ,svg:Some(AttrMapEntry::AllNamespaceElements(
      AttributeMinification {
        boolean: false,
        case_insensitive: false,
        collapse: false,
        default_value: None,
        redundant_if_empty: true,
        trim: false,
      }
    )),});
          AttrMap::new(m)
        };
      }
    