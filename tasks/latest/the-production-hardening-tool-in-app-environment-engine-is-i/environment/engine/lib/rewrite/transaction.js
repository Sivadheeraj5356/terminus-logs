'use strict';

const fs = require('fs');
const path = require('path');

function writeTransaction(writes) {
  const staged = writes.map(({ file, content }) => {
    const temp = path.join(path.dirname(file), `.${path.basename(file)}.${process.pid}.tmp`);
    fs.writeFileSync(temp, content, 'utf8');
    return { file, temp };
  });
  try {
    for (const { file, temp } of staged) fs.renameSync(temp, file);
  } catch (error) {
    for (const { temp } of staged) if (fs.existsSync(temp)) fs.unlinkSync(temp);
    throw error;
  }
}

module.exports = { writeTransaction };
