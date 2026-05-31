import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";

export function useConversationRouter() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const conversationIdFromUrl = id ?? null;

  const navigateToConversation = useCallback(
    (convId: string) => navigate(`/c/${convId}`),
    [navigate],
  );

  const navigateToSplash = useCallback(
    () => navigate("/"),
    [navigate],
  );

  const navigateReplace = useCallback(
    (path: string) => navigate(path, { replace: true }),
    [navigate],
  );

  return {
    conversationIdFromUrl,
    navigateToConversation,
    navigateToSplash,
    navigateReplace,
  };
}
