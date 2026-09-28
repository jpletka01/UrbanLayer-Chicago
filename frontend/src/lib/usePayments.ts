import { useEffect, useState } from "react";
import { fetchPaymentsStatus, type PaymentsStatus } from "./api";

/** Purchase availability; null until known. Callers show the normal purchase
 *  UI while null (the request is tiny and cached) and "coming soon" when a
 *  purchase type is off. */
export function usePayments(): PaymentsStatus | null {
  const [status, setStatus] = useState<PaymentsStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetchPaymentsStatus().then((s) => {
      if (!cancelled) setStatus(s);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return status;
}
