import crypto from 'crypto';

export function stdoutDigest(text: string): string {
  return crypto.createHash('sha256').update(text).digest('hex').slice(0, 16);
}
