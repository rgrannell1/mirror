
export class MirrorAPI {
  constructor(port) {
    this.port = port;
  }
  async getPhotoMetadata(id) {
    const res = await fetch(`http://localhost:${this.port}/photo/${id}/metadata`, {
      headers: {
        'Content-Type': 'application/json'
      },
    });

    try {
      const body = await res.json();
      return body;
    } catch (err) {
      console.error(`failed to retrieve json for metadata request`);
    }
  }

  async photoCount() {
    const res = await fetch(`http://localhost:${this.port}/photos/count`, {
      headers: {
        'Content-Type': 'application/json'
      },
    });

    try {
      const body = await res.json();
      return body.count;
    } catch (err) {
      console.error(`failed to retrieve json for metadata request`);
    }
  }
}
