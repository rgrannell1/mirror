#!/usr/bin/python3
"""
Usage:
  mirror tag --metadata=<fpath>                         <dir>
  mirror tag-faces --metadata=<fpath> [--exclude=<str>] <dir>
  mirror list-tags --metadata=<fpath> [--graphvis]      <dir>
  mirror list-tagfiles [--tag=<tag>]                    <dir>
  mirror list-photos [--tag=<tag>]                      <dir>
  mirror publish --metadata=<fpath>                     <dir> <manifest>
  mirror feed --metadata=<fpath>                        <dir> <outdir>
  mirror (-h | --help)

Description:
  Mirror publishes & manages photo-libraries.

  - Indexes media into a SQLite "manifest" database.
  - Generates tagfiles, which are YAML files containing metadata for media.
  - Calculates image-blur
  - Optionally applies face-recognition to the media library
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
  tag                Tag all images in a directory based on the tags.md files. Tag albums with
                       a title, cover-image, and other information

  tag-faces          Tag faces in a directory.

  list-tags          List all tags in a directory.

  list-photos        List photos and tag information. Optionally filter for a specific tag.

  list-tagfiles      List all tag-files in a directory. Optionally filter for a specific tag.

  publish            Publish images to Spaces, and generate a manifest-file.

  feed               Generate a directory of JSONFeed's for a directory

Options:
  --graphvis            Output a graphvis file.
  --metadata=<fpath>    The path to a YAML file containing metadata.
  --tag=<tag>           The tag to list photos for.
  -h, --help            Show this screen.

"""
from docopt import docopt
from src.mirror import Mirror

if __name__ == '__main__':
  args = docopt(__doc__)

  if args['tag']:
    Mirror.tag(args['<dir>'], args['--metadata'])
  elif args['list-tags']:
    Mirror.list_tags(args['<dir>'], {
        'graphvis': args['--graphvis'],
        'metadata': args['--metadata']
    })
  elif args['list-photos']:
    Mirror.list_photos(args['<dir>'], args['--metadata'], args['--tag'])
  elif args['publish']:
    Mirror.publish(args['<dir>'], args['--metadata'], args['<manifest>'])
  elif args['feed']:
    Mirror.feed(args['<dir>'], args['--metadata'], args['<outdir>'])
  elif args['list-tagfiles']:
    Mirror.list_tagfiles(args['<dir>'], args['--tag'])
  elif args['tag-faces']:
    Mirror.tag_faces(args['<dir>'], args['--metadata'], args['--exclude'])
  else:
    print(__doc__)
    exit(1)
