# media-moderation-api

This local Express service classifies uploaded media with the bundled
TensorFlow.js model. It has no network model dependency.

## Running

```bash
npm ci
node server.js
```

`GET /health` reports liveness. `POST /moderate` accepts one multipart `image`
upload and returns a label, confidence, and policy-derived moderation result.
Runtime policy is loaded from `config/inference.js`; Terraform deployment
defaults are maintained under `terraform/`.

The hardening utility is available through `cli/harden.js` and the library
export in `index.js`. It consumes a local decision export, the fixture manifest,
and the bundled model to produce deployment and fixture audit artifacts.
