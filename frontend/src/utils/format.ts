/** Pure display formatting only — never parses a value in order to
 * recompute or compare it. Monetary values stay strings end-to-end (backend
 * Decimal -> JSON string -> here -> screen) so no float ever enters the
 * pipeline. */

/** "gross_salary" -> "Gross salary", "SLAB_TAX:SLAB_1" -> "Slab tax slab 1".
 * Cosmetic label-casing only, not a lookup of what any field means. */
export function humanizeLabel(code: string): string {
  const words = code.toLowerCase().replace(/[_:]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Prefixes a backend decimal string with the Rupee sign. Never touches the
 * digits themselves, so precision is exactly what the backend sent. */
export function formatCurrency(amount: string): string {
  return `₹${amount}`
}
