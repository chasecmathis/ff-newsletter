const WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
  "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
  "seventeen", "eighteen", "nineteen", "twenty",
];

/** Spell small numbers out — headline copy reads better in words than digits. */
export function numberWord(n: number): string {
  return WORDS[n] ?? String(n);
}

export function titleCaseNumber(n: number): string {
  const word = numberWord(n);
  return word.charAt(0).toUpperCase() + word.slice(1);
}
