"""SQL queries for photo semantic triples."""

# Select the best mosaic banner for each album.
ALBUM_BANNER_QUERY = """
    SELECT fpath, album_id, mosaic_banner_url
    FROM (
        SELECT
            vps.fpath,
            vpd.album_id,
            ep.url AS mosaic_banner_url,
            ROW_NUMBER() OVER (
                PARTITION BY vpd.album_id
                ORDER BY
                    {rating_order} DESC,
                    {genre_order} ASC
            ) AS rank
        FROM view_photo_metadata_summary vps
        JOIN view_photo_data vpd ON vps.fpath = vpd.fpath
        JOIN encoded_photos ep ON vps.fpath = ep.fpath AND ep.role = 'mosaic_banner'
        WHERE vpd.album_id IS NOT NULL
    )
    WHERE rank = 1
"""
