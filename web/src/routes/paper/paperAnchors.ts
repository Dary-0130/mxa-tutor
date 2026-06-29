function hashCodePoints(input: string): string {
  let hash = 0x811c9dc5;
  for (const char of input) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(36);
}

export function makePlanMappingAnchorId(
  rowIndex: number,
  paperParamName: string,
  modelParamName: string,
): string {
  const hash = hashCodePoints(`${paperParamName}|${modelParamName}`);
  return `paper-param-map-${rowIndex}-${hash}`;
}

export function makeMissingPromptAnchorId(promptId: string): string {
  return `paper-param-missing-${promptId}`;
}
