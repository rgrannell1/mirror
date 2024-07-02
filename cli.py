#!/usr/bin/python3
"""
Usage:
  mirror tag
  mirror tag --metadata=<fpath>                                <dir>
  mirror list-tags [--graphvis]
  mirror list-tags --metadata=<fpath> [--graphvis]             <dir>
  mirror list-tagfiles [--tag=<tag>]
  mirror list-tagfiles [--tag=<tag>]                           <dir>
  mirror show-tagfiles [--tag=<tag>]
  mirror show-tagfiles [--tag=<tag>]                           <dir>
  mirror list-photos [--tag=<tag>] [--from=<from>] [--to=<to>]
  mirror list-photos --metadata=<fpath> [--tag=<tag>] [--from=<from>] [--to=<to>] <dir>
  mirror publish
  mirror publish --metadata=<fpath>                            <dir> <manifest>
  mirror add-google-photos-metadata <google-photos-file>
  mirror add-google-photos-metadata --metadata=<fpath>         <dir> <google-photos-file>
  mirror add-google-vision-metadata --metadata=<fpath>         <dir>
  mirror add-google-vision-metadata
  mirror feed                                                  <outdir>
  mirror feed --metadata=<fpath>                               <dir> <outdir>
  mirror (-h | --help)

Description:
  Mirror publishes & manages photo-libraries.

  - Indexes media into a SQLite "manifest" database.
  - Generates tagfiles, which are YAML files containing metadata for media.
  - Calculates image-blur
  - Syncs information from tagfiles onto photos and other media.
  - Publishes a subset of media to DigitalOcean Spaces after transcoding to web-friendly formats.
  - Generates subscribable JSONFeed's for directories of media.
  - Publishes JSON artifacts to a chosen directory describing the published media.

  ++ Photo Settings ++

  * user.xyz.rgrannell.photos.fstop               the f-stop of a photo
  * user.xyz.rgrannell.photos.focal_equivalent    the equivalnet focal length of a photo
  * user.xyz.rgrannell.photos.model               the camera model
  * user.xyz.rgrannell.photos.iso                 the ISO of a photo
  * user.xyz.rgrannell.photos.width               the width of an image in pixels
  * user.xyz.rgrannell.photos.height              the height of an image in pixels
  * user.xyz.rgrannell.photos.tags                a CSV of tag-data.

  ++ Album Information ++

  * user.xyz.rgrannell.photos.album_title          the title of a photo-album
  * user.xyz.rgrannell.photos.album_cover          the path of a cover-image for a photo-album
  * user.xyz.rgrannell.photos.album_description    an album description
  * user.xyz.rgrannell.photos.geolocation          the geolocation of a photo-album, in GeoJSON format

Commands:
  add-google-photos-metadata    Add scraped google metadata to the database.

  add-google-vision-metadata    Add google-vision metadata to the database.

  tag                           Tag all images in a directory based on the tags.md files. Tag albums with
                                  a title, cover-image, and other information

  list-tags                     List all tags in a directory.

  list-photos                   List photos and tag information. Optionally filter for a specific tag.

  list-tagfiles                 List all tag-files in a directory. Optionally filter for a specific tag.

  show-tagfiles                 Show all tag-files in a directory. Optionally filter for a specific tag.

  publish                       Publish images to Spaces, and generate a manifest-file.

  feed                          Generate a directory of JSONFeed's for a directory.


Options:
  --graphvis            Output a graphvis file.
  --metadata=<fpath>    The path to a YAML file containing metadata.
  --tag=<tag>           The tag to list photos for.
  --from=<from>         The start of a date-range.
  --to=<to>             The end of a date-range.
  -h, --help            Show this screen.

"""
from docopt import docopt
from src.config import MirrorConfig
from src.mirror import Mirror

if __name__ == '__main__':
  args = docopt(__doc__)
  cfg = MirrorConfig.read(args)

  if args['tag']:
    Mirror.tag(cfg.directory, cfg.metadata)
  elif args['list-tags']:
    Mirror.list_tags(cfg.directory, {
        'graphvis': args['--graphvis'],
        'metadata': cfg.metadata
    })
  elif args['list-photos']:
    Mirror.list_photos(cfg.directory, cfg.metadata, args['--tag'], args['--from'], args['--to'])
  elif args['publish']:
    Mirror.publish(cfg.directory, cfg.metadata, cfg.manifest)
  elif args['feed']:
    Mirror.feed(cfg.directory, cfg.metadata, args['<outdir>'])
  elif args['list-tagfiles']:
    Mirror.list_tagfiles(cfg.directory, args['--tag'])
  elif args['show-tagfiles']:
    Mirror.show_tagfiles(cfg.directory, args['--tag'])
  elif args['add-google-photos-metadata']:
    Mirror.add_google_photos_metadata(cfg.directory, cfg.metadata, args['<google-photos-file>'])
  elif args['add-google-vision-metadata']:
    Mirror.add_google_vision_metadata(cfg.directory, cfg.metadata)
  else:
    print('Invalid command')
    print(__doc__)
    exit(1)
