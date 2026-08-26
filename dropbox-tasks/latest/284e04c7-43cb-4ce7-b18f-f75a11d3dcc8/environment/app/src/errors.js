export class ContractError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ContractError';
    this.code = code;
  }
}

export class UsageError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UsageError';
  }
}
