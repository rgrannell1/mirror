
export class PageLocation {
  static showPhotoUrl(id) {
    window.location.hash = `#/photo/${id}`;
    document.title = "Mirror - photos";
  }

  static getUrl() {
    return {
      type: "home",
      id: window.location.hash.split("/")[2],
    };
  }
}
