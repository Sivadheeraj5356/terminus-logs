'use strict';

const express = require('express');
const disputes = require('./routes/disputes');

const app = express();
app.use(express.json());
app.use('/v1', disputes);

module.exports = app;
