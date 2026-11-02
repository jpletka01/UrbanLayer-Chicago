// Below Tailwind's `md` (768 px): the Profile's phone layout (single-open sections, the place-map strip).
// Follows the window as it resizes or rotates; false where matchMedia is missing (tests, SSR).
import { useEffect, useState } from "react";

const PHONE_QUERY = "(max-width: 767px)";

export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(() => typeof window !== "undefined" && window.matchMedia?.(PHONE_QUERY).matches === true);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia(PHONE_QUERY);
    const onChange = () => setPhone(query.matches);
    onChange();
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return phone;
}
