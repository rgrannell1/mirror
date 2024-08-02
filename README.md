
# Mirror

Bulk-tag a photo-library

```sh
  mirror create-manifest                           <dir>
  mirror tag --metadata=<fpath>                    <dir>
  mirror list-tags --metadata=<fpath> [--graphvis] <dir>
  mirror list-tagfiles [--tag=<tag>]               <dir>
  mirror list-photos [--tag=<tag>]                 <dir>
  mirror publish --metadata=<fpath>                <dir> <manifest>
  mirror feed --metadata=<fpath>                   <dir> <outdir>
  mirror (-h | --help)
```

Start the server

```sh
flask --app src/server/app.py run
```

## Overview

Mirror uses a yaml file impersonating a markdown file to store information about images in an album. Information like descriptions, tags and geolocations can be manually added to these `tags.md` files with help from a markdown supporting editor. Mirror then associates this metadata onto photos using [extended-attributes](https://en.wikipedia.org/wiki/Extended_file_attributes). Finally, it uploads this media to DigitalOcean Spaces and publishes metadata files locally.

## Installation

## License

The MIT License

Copyright (c) 2023 Róisín Grannell

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
