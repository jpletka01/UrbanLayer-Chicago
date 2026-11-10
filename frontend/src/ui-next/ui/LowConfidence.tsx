// "Low confidence" that explains itself: the label is the trigger, and hovering it (a mouse) or tapping it (touch)
// opens its definition (owner's third review of Neighborhood, Item 102: the tag was defined only once, far below).
import { useTranslation } from "react-i18next";
import { EqualApproximately } from "lucide-react";
import { Toggletip } from "../../components/ui/Toggletip";
import { StatusLabel } from "../../components/ui/StatusLabel";

export function LowConfidence({ definition, testId }: { definition?: string; testId?: string }) {
  const { t } = useTranslation("next");
  const { t: tc } = useTranslation("common");
  return (
    <span className="inline-flex" data-testid={testId} data-confidence-state="low">
      <Toggletip kind="info" label={t("lowConfidence.label")} visible={<StatusLabel tone="warning" glyph={EqualApproximately}>{tc("confidence.kind.low")}</StatusLabel>}>
        {definition ?? t("lowConfidence.census")}
      </Toggletip>
    </span>
  );
}
