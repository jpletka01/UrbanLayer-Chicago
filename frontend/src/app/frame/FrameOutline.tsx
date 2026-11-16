// The frame's outline while the browser downloads a new page's code (Item 89: that moment was a blank page). The
// side panel and header in their final sizes, a faint body, nothing interactive. Lives in the main bundle with
// `VersionedRoute`, so it imports nothing from the lazily loaded pages.
export function FrameOutline() {
  const bar = "block rounded bg-nx-ink/10 motion-safe:animate-pulse";
  return (
    <div className="ui-next flex min-h-dvh bg-nx-page" aria-busy="true" data-testid="frame-outline">
      <div aria-hidden className="sticky top-0 hidden h-dvh w-[212px] shrink-0 flex-col gap-3 border-r border-nx-ink/10 px-5 py-6 lg:flex">
        <span className="mb-3 flex items-center gap-2"><span className="h-6 w-6 rounded-full bg-nx-ink/20" /><span className={`${bar} h-3 w-20`} /></span>
        {[0, 1, 2].map((i) => <span key={i} className={`${bar} h-4 w-28`} />)}
      </div>
      <div aria-hidden className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-[68px] items-center border-b border-nx-ink/10 px-4 sm:px-7"><span className={`${bar} h-3 w-40`} /></div>
        <div className="flex flex-col gap-5 px-4 pt-5 sm:px-7 sm:pt-7">
          <span className="block h-52 rounded-2xl bg-nx-block sm:h-64 lg:h-72" />
          <span className={`${bar} h-6 w-full max-w-2xl`} />
        </div>
      </div>
    </div>
  );
}
