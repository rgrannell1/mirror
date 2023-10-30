#!/usr/bin/python3

"""
Usage:
  mirror init                      <dir>
  mirror create-manifest           <dir>
  mirror tag --metadata=<fpath>    <dir>
  mirror list-tags                 <dir>
  mirror list-photos [--tag=<tag>] <dir>
  mirror publish                   <dir> <manifest>
  mirror (-h | --help)

Description:
  Mirror is a tool for tagging thousands of images, sorting them into albums, publishing a subset,
  sycing the images in web-friendly format to DigitalOcean Spaces, and generating a manifest-file
  that can be used to generate a static website.

Tags:
  * user.xyz.rgrannell.photos.tags           a CSV of tag-data.
  * user.xyz.rgrannell.photos.album_title    the title of a photo-album
  * user.xyz.rgrannell.photos.album_cover    the path of a cover-image for a photo-album

Commands:
  init         Initialize a directory with tags.md files. Old tags.md files will be moved to
                 a backup file.

  tag          Tag all images in a directory based on the tags.md files. Tag albums with
                  a title, cover-image, and other information

  list-tags    List all tags in a directory.

  list-photos  List photos and tag information. Optionally filter for a specific tag.

  publish      Publish images to Spaces, and generate a manifest-file

Options:
  --metadata=<fpath>  The path to a YAML file containing metadata.
  --tag=<tag>         The tag to list photos for.
  -h, --help           Show this screen.
"""
from docopt import docopt
from src.mirror import Mirror

if __name__ == '__main__':
  args = docopt(__doc__)

  if args['init']:
    Mirror.init(args['<dir>'])
  elif args['tag']:
    Mirror.tag(args['<dir>'], args['--metadata'])
  elif args['list-tags']:
    Mirror.list_tags(args['<dir>'])
  elif args['list-photos']:
    Mirror.list_photos(args['<dir>'], args['--tag'])
  elif args['publish']:
    Mirror.publish(args['<dir>'], args['<manifest>'])
  else:
    print(__doc__)
    exit(1)
