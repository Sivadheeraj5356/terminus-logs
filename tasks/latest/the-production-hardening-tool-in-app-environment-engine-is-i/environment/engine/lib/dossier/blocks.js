'use strict';

function splitBlocks(text) {
  return text.split(/(?=^Record:\s+)/m).filter((block) => /^Record:\s+/m.test(block));
}

module.exports = { splitBlocks };
