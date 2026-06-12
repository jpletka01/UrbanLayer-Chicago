import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";

export function useConversationRouter() {
  const { id, shareToken } = useParams<{ id?: string; shareToken?: string }>();
  const navigate = useNavigate();

  const conversationIdFromUrl = id ?? null;
  const shareTokenFromUrl = shareToken ?? null;

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

  const navigateBack = useCallback(
    () => navigate(-1),
    [navigate],
  );

  return {
    conversationIdFromUrl,
    shareTokenFromUrl,
    navigateToConversation,
    navigateToSplash,
    navigateReplace,
    navigateBack,
  };
}
