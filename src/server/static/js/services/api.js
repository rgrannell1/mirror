
export class MirrorAPI {
  constructor(port) {
    this.port = port;
  }
  async getPhotoMetadata(id) {
    const res = await fetch(`http://localhost:${this.port}/photo/${id}/metadata`, {
      mode: 'no-cors'
    });

    const body = await res.json();

    return body;
  }

  async photoCount() {
    const res = await fetch(`http://localhost:${this.port}/photos/count`, {
      mode: 'no-cors'
    });

    const body = await res.json();

    return body.count;
  }
}
