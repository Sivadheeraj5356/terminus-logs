export function rotationDecision(envelopeVersion, activeVersion, minimumReadableVersion) {
  if (envelopeVersion < minimumReadableVersion) return 'retired';
  if (envelopeVersion > activeVersion) return 'future';
  return envelopeVersion < activeVersion ? 'rotate' : 'current';
}
