The albums.md file currently has a `country` column where each album is tagged with human-readable country names like "Ireland" or "Germany". These get looked up by slug to resolve canonical place URNs, and are emitted as `country` relation triples for albums.

The system should instead use a `places` column in albums.md, where album place values are stored directly as place URNs (e.g. `urn:ró:place:148`) matching the existing format used in photos.md. This removes the need for the slug-to-URN lookup at build time and allows albums to be associated with any place in things.toml, not just those with a country feature.

The DB relation storing album place flags changes from `county` to `places`, and the semantic triple relation emitted for albums changes from `country` to `location`. All existing albums retain their place associations, expressed as place URNs rather than plain text.

The frontend (photos.rgrannell.xyz) is updated to read the `location` relation on albums rather than `country`, and to display place links using the existing place/country link components. The country filter on the albums page continues to work as before, since the place URNs for country-level places are unchanged.
