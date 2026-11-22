import { useEffect } from "react";

/** Automatically invoke `onRefresh` whenever LOOMOS AI Copilot or another panel updates live shed data. */
export function useLiveRefresh(onRefresh: () => void | Promise<void>) {
  useEffect(() => {
    const handler = () => {
      void onRefresh();
    };
    window.addEventListener("loomos:data-updated", handler);
    return () => window.removeEventListener("loomos:data-updated", handler);
  }, [onRefresh]);
}
