export function DisclaimerBanner() {
  return (
    <div className="flex gap-3 items-start p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 text-sm leading-relaxed mt-4">
      <span className="text-base">💡</span>
      <p>
        <strong>Notice:</strong> This information is based on official city documents but does not constitute legal advice. Please consult a licensed attorney or contact the relevant city department for official guidance.
      </p>
    </div>
  );
}
