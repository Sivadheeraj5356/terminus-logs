# Path Normalization Notes

Routes are dispatched using a canonicalized path:
- percent-decoding up to bounded iterations
- slash collapsing
- lowercase canonical form
- path cleaning

Authorization checks must use the same canonical representation as dispatch.
