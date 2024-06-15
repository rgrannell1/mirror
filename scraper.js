
// paste me into the console.

var results = []

function giveMeMyBloodyDataBack() {
  const result = {
    fpath: $('div[aria-label^="Filename"]')?.innerText,
    location:  $('div[aria-label="Edit location"]')?.innerText,
    mapHref: $('a[title="Show location of photo on Google Maps"]')?.href
  };

  results.push(result)

  $('div[aria-label="View next photo"]').click()
  console.log(result)

  setTimeout(() => {
    giveMeMyBloodyDataBack()
  }, 750)
}

giveMeMyBloodyDataBack()
