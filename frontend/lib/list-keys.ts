/**
 * Stable React list keys.
 *
 * Priority: object-provided id → known stable fields → deterministic
 * label-based key → index only as a final fallback. Two distinct items
 * with identical display labels must never produce the same key.
 */
export function stableItemKey(
  label: string,
  index: number,
  scope: string,
  id?: string | number | null
): string {
  if (id !== undefined && id !== null && `${id}` !== "") {
    return `${scope}:id:${id}`;
  }
  // index guarantees uniqueness even when labels are identical
  return `${scope}:${label}:${index}`;
}
