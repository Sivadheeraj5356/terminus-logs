// server.js
const express = require('express');
const app = express();

const authRoutes = require('./routes/auth');
const itemRoutes = require('./routes/items');
const smsRoutes = require('./routes/sms');

app.use(express.json());

app.use('/api/auth', authRoutes);
app.use('/api/items', itemRoutes);

// SMS route mount
app.use('/api/sms', smsRoutes);

module.exports = app;
