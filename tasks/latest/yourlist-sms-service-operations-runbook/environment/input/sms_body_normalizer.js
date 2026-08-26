// middleware/sms_body_normalizer.js
// Maps legacy `to` field to `user` before the send handler runs.
// NOTE: This file is NOT wired in server.js or routes/sms.js in this snapshot.

function normalizeSmsBody(req, _res, next) {
  if (req.body && req.body.to && !req.body.user) {
    req.body.user = req.body.to;
    delete req.body.to;
  }
  next();
}

module.exports = { normalizeSmsBody };
