
import { html, LitElement, until } from "../library/lit.js";

import { MirrorAPI } from "../services/api.js";
import { PageLocation } from "../services/location.js";

export class MirrorApp extends LitElement {
  static get properties() {
    return {
      id: { type: Number },
      metadata: { type: Object }
    };
  }
  connectedCallback() {
    super.connectedCallback();
    this.setStateFromUrl();
    window.addEventListener("popstate", this.handlePopState.bind(this));
    document.addEventListener('keydown', this.handleKeyDown.bind(this));
  }

  setStateFromUrl() {
    const location = PageLocation.getUrl();

    if (location.type === 'photo') {
      if (location.id !== undefined) {
        this.id = location.id;
        this.requestUpdate();
      }
    }
  }

  handlePopState() {
    this.setStateFromUrl();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener('keydown', this.handleKeyDown.bind(this));
    window.removeEventListener("popstate", this.handlePopState.bind(this));
  }

  handleKeyDown(event) {
    if (event.key === 'ArrowLeft') {
      this.id--;
      PageLocation.showPhotoUrl(this.id);
      this.requestUpdate();
    } else if (event.key === 'ArrowRight') {
      this.id++;
      PageLocation.showPhotoUrl(this.id);
      this.requestUpdate();
    }
  }
  url() {
    return `/photo/${this.id}`
  }
  async renderTags(id) {
    const client = new MirrorAPI(5000);
    const metadata = await client.getPhotoMetadata(id);

    return html`<ul>${
      metadata.tags.map(tag => html`<li>${tag}</li>`)
    }</ul>`
  }

  async renderDescription(id) {
    const client = new MirrorAPI(5000);
    const metadata = await client.getPhotoMetadata(id);

    return html`<p>unimplemented</h>`
  }

  async renderFilePath(id) {
    const client = new MirrorAPI(5000);
    const metadata = await client.getPhotoMetadata(id);

    return html`<p>${ metadata.path }</p>`
  }

  async renderRating(id) {
    const client = new MirrorAPI(5000);
    const metadata = await client.getPhotoMetadata(id);

    return html`<p>⭐⭐⭐⭐⭐</p>`
  }

  render() {
    return html`
      <div>
        <h1>Mirror</h1>

        Shortcuts:
        <ul>
          <li><kbd>←</kbd> Previous</li>
          <li><kbd>→</kbd> Next</li>
        </ul>

        <image width="800" src="${this.url()}"></image>

        <h2>File Path</h2>

        ${
          until(
            this.renderFilePath(this.id),
            html`<p>Loading...</p>`
          )
        }

        <h2>Description</h2>

        ${
          until(
            this.renderDescription(this.id),
            html`<p>Loading...</p>`
          )}

        <h2>Tags</h2>
        ${
          until(
            this.renderTags(this.id),
            html`<p>Loading...</p>`
          )}

        <h2>Rating</h2>
        ${
          until(
            this.renderRating(this.id),
            html`<p>Loading...</p>`
          )
        }
      </div>
    `;
  }
}

customElements.define('mirror-app', MirrorApp);
