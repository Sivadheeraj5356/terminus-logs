// services/smsService.js
'use strict';

const Telnyx = require('telnyx');

function getClient() {
  if (!process.env.TELNYX_API_KEY) {
    throw new Error('TELNYX_API_KEY is not configured');
  }
  return Telnyx(process.env.TELNYX_API_KEY);
}

function resolveFromNumber() {
  if (process.env.TELNYX_PHONE_NUMBER) {
    return process.env.TELNYX_PHONE_NUMBER;
  }
  if (process.env.TELNYX_FROM_NUMBER) {
    return process.env.TELNYX_FROM_NUMBER;
  }
  return '';
}

class SMSService {
  static async sendSMS(user, message) {
    const from = resolveFromNumber();
    if (!from) {
      const err = new Error('Invalid from number');
      err.errors = [{ code: '40304', title: 'Invalid from number' }];
      throw err;
    }

    const client = getClient();
    return client.messages.create({
      from,
      to: user,
      text: message
    });
  }
}

module.exports = SMSService;
