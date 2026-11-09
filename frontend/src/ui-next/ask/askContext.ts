// How a block on a Profile tab hands a question to the analyst (decision Item 99): the page provides it, a `Term`
// calls it. It opens the Ask drawer with the question written in the box, never sends it (a visitor sends; no
// model call happens until they do). `ready` is false until every Profile part is in, like the Ask button.
import { createContext, useContext } from "react";

export interface AskHandoff {
  ready: boolean;
  /** The parcel's address, so a question carries it (a "this lot" question routes to clarification). */
  address: string;
  open: (question: string) => void;
  /** Opens a program's page in the same right panel (Item 99), in place of the analyst. */
  openProgram?: (program: "tif" | "oz" | "ez" | "qct" | "nmtc") => void;
}

export const AskContext = createContext<AskHandoff | null>(null);
export const useAskHandoff = () => useContext(AskContext);
