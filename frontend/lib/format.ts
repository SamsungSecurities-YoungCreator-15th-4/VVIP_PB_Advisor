// 금액(만원) 표시 유틸 — 1억(=10,000만) 이상이면 "x억"으로, 미만이면 "x만원"으로.
// 예: 50000 → "5억", 33280 → "3.33억", 1142 → "1,142만원", -180 → "-180만원"

/** 부호 없이 절대값을 {value, unit}로 분해 (헤드라인 등 큰 숫자/작은 단위 분리용). */
export function splitManwon(manwon: number): { value: string; unit: string } {
  const abs = Math.abs(Math.round(manwon));
  if (abs >= 10000) {
    // 억 단위: 소수점 2자리까지, 불필요한 0 제거 (1.15억 / 5억)
    const eok = parseFloat((abs / 10000).toFixed(2));
    return { value: eok.toLocaleString(), unit: "억" };
  }
  return { value: abs.toLocaleString(), unit: "만원" };
}

/** 부호 포함 전체 문자열. withWon=false면 만원 단위에서 "원"을 떼어 "만"만 표기(차트 라벨용). */
export function formatManwon(
  manwon: number,
  opts?: { withWon?: boolean },
): string {
  const sign = Math.round(manwon) < 0 ? "-" : "";
  const { value, unit } = splitManwon(manwon);
  const u = opts?.withWon === false && unit === "만원" ? "만" : unit;
  return `${sign}${value}${u}`;
}
