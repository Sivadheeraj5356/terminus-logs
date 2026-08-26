// routes/sms.js
const express = require('express');
const router = express.Router();
const SMSService = require('../services/smsService');
const { authenticateToken } = require('../middleware/auth');

router.use(express.json());

router.get('/test-config', authenticateToken, async (req, res) => {
  const config = {
    apiKey: process.env.TELNYX_API_KEY ? 'Set' : 'Missing',
    fromNumber: process.env.TELNYX_PHONE_NUMBER ? 'Set' : 'Missing'
  };

  res.json({
    config,
    ready: !!(process.env.TELNYX_API_KEY && process.env.TELNYX_PHONE_NUMBER)
  });
});

router.post('/send', authenticateToken, async (req, res) => {
  const { user, message, countryCode = 'US' } = req.body;

  try {
    if (!user) {
      return res.status(400).json({
        success: false,
        error: 'Phone number (user) is required'
      });
    }

    if (!message) {
      return res.status(400).json({
        success: false,
        error: 'Message is required'
      });
    }

    const result = await SMSService.sendSMS(user, message);

    res.json({
      success: true,
      id: result.id,
      status: 'queued',
      to: result.to,
      from: result.from
    });
  } catch (err) {
    console.error('SMS send error:', {
      message: err.message,
      errors: err.errors
    });

    res.status(500).json({
      success: false,
      error: err.message
    });
  }
});

router.post('/webhook', async (req, res) => {
  try {
    const event = req.body;
    console.log('Telnyx webhook received:', JSON.stringify(event, null, 2));

    if (event && event.data) {
      const { event_type, payload } = event.data;
      const messageId = payload.id;

      if (event_type === 'message.failed') {
        console.error('Message failed:', payload.errors);
      }

      if (event_type === 'message.delivered') {
        console.log('Message delivered:', messageId);
      }
    }

    res.sendStatus(200);
  } catch (err) {
    console.error('Telnyx webhook error:', err);
    res.sendStatus(200);
  }
});

module.exports = router;
