export function currentQuarter(): string {
  const now = new Date();
  const y = now.getFullYear();
  const q = Math.ceil((now.getMonth() + 1) / 3);
  return `${y}Q${q}`;
}

export function listRecentQuarters(count = 8): string[] {
  const quarters: string[] = [];
  const now = new Date();
  let y = now.getFullYear();
  let q = Math.ceil((now.getMonth() + 1) / 3);
  for (let i = 0; i < count; i++) {
    quarters.push(`${y}Q${q}`);
    q--;
    if (q === 0) { q = 4; y--; }
  }
  return quarters;
}
