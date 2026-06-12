import { useEffect, useRef, useState } from "react";

/**
 * 뷰포트 너비가 collapseBelow 미만이 되면 패널을 자동으로 닫는 훅.
 * - 화면이 다시 넓어져도 자동으로 열지 않음 (사용자가 수동으로 열어야 함)
 * - 수동으로 연 후 창 크기를 조절해도 다시 닫히지 않음 — 기준치를 위→아래로 교차하는 순간에만 닫힘
 * - SSR 안전: 서버에서는 true(열림)로 초기화, 마운트 후 실제 뷰포트 기준으로 보정
 */
export function useAutoCollapse(
  collapseBelow: number,
): [boolean, React.Dispatch<React.SetStateAction<boolean>>] {
  const [isOpen, setIsOpen] = useState(true);
  const prevWidthRef = useRef<number | null>(null);

  useEffect(() => {
    prevWidthRef.current = window.innerWidth;
    if (window.innerWidth < collapseBelow) setIsOpen(false);

    const check = () => {
      const curr = window.innerWidth;
      const prev = prevWidthRef.current;
      if (prev !== null && prev >= collapseBelow && curr < collapseBelow) {
        setIsOpen(false);
      }
      prevWidthRef.current = curr;
    };

    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [collapseBelow]);

  return [isOpen, setIsOpen];
}
