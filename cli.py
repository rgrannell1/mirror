#!/usr/bin/python3

"""
Usage:
  mirror init                      <dir>
  mirror tag --metadata=<fpath>    <dir>
  mirror list-tags                 <dir>
  mirror list-photos [--tag=<tag>] <dir>
  mirror (-h | --help)

Description:


Tags:
  * user.xyz.rgrannell.photos.tags    a CSV of tag-data.

Commands:
  init         Initialize a directory with tags.md files. Old tags.md files will be moved to
                 a backup file.

  tag          Tag all images in a directory based on the tags.md files.

  list-tags    List all tags in a directory.

  list-photos  List photos and tag information. Optionally filter for a specific tag.

Options:
  --metadata=<fpath>  The path to a YAML file containing metadata.
  --tag=<tag>         The tag to list photos for.
  -h, --help           Show this screen.
"""
from docopt import docopt
import src.mirror as Mirror

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
  else:
    print(__doc__)
    exit(1)
