#!/usr/bin/python3

"""
Usage:
  mirror create-manifest                           <dir>
  mirror tag --metadata=<fpath>                    <dir>
  mirror list-tags --metadata=<fpath> [--graphvis] <dir>
  mirror list-photos [--tag=<tag>]                 <dir>
  mirror publish --metadata=<fpath>                <dir> <manifest>
  mirror feed                                      <dir> <feed>
  mirror (-h | --help)

Description:
  Mirror is a tool for tagging thousands of images, sorting them into albums, publishing a subset,
  sycing the images in web-friendly format to DigitalOcean Spaces, and generating a manifest-file
  that can be used to generate a static website.

Tags:



  * user.xyz.rgrannell.photos.tags           a CSV of tag-data.

  ++ Photo Settings ++

  * user.xyz.rgrannell.photos.fstop
  * user.xyz.rgrannell.photos.focal_equivalent
  * user.xyz.rgrannell.photos.model
  * user.xyz.rgrannell.photos.iso

  ++ Album Information ++

  * user.xyz.rgrannell.photos.album_title    the title of a photo-album
  * user.xyz.rgrannell.photos.album_cover    the path of a cover-image for a photo-album

  ++ Image Dimensions ++

  * user.xyz.rgrannell.photos.width     the width of an image in pixels
  * user.xyz.rgrannell.photos.height    the height of an image in pixels

  ++ Location Information ++

  * user.xyz.rgrannell.photos.location_address    a human-readable address
  * user.xyz.rgrannell.photos.location_latitude   a latitude coordinate
  * user.xyz.rgrannell.photos.location_longitude  a longitude coordinate

Commands:
  create-manifest    Create a manifest-file for a directory. This file can be used to generate

  tag                Tag all images in a directory based on the tags.md files. Tag albums with
                       a title, cover-image, and other information

  list-tags          List all tags in a directory.

  list-photos        List photos and tag information. Optionally filter for a specific tag.

  publish            Publish images to Spaces, and generate a manifest-file

  feed               Generate a feed-file for a directory

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
    Mirror.feed(args['<dir>'], args['<feed>'])
  else:
    print(__doc__)
    exit(1)
