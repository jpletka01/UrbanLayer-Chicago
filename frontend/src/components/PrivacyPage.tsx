import PageHeader from "./PageHeader";

// English-only by design, like the About page — legal/reference surface,
// excluded from the i18n namespaces.

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="text-subtitle font-semibold text-text-primary mb-3">{title}</h2>
      {children}
    </section>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-text-secondary leading-relaxed mb-3">{children}</p>;
}

function Li({ children }: { children: React.ReactNode }) {
  return <li className="text-text-secondary leading-relaxed">{children}</li>;
}

export function PrivacyPage() {
  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <PageHeader />
      <article className="max-w-3xl mx-auto py-12 px-6 pb-32">
        <h1 className="text-section font-semibold tracking-tight mb-2">Privacy Policy</h1>
        <p className="text-caption text-text-muted mb-10">Last updated: July 5, 2026</p>

        <Section title="The short version">
          <P>
            UrbanLayer is a site-feasibility tool for Chicago real estate. We collect the minimum
            we need to run the product and understand how it's used: our own usage analytics, the
            account details you give us when you sign in, and payment records handled by Stripe.
            We do not sell or share your personal data with data brokers or advertisers.
          </P>
        </Section>

        <Section title="What we collect">
          <ul className="list-disc pl-5 space-y-2 mb-3">
            <Li>
              <strong className="text-text-primary">Usage analytics (first-party).</strong> We run
              our own lightweight analytics — no advertising trackers. Events like page views,
              searches, and button clicks are recorded with a random visitor ID stored in your
              browser, the page you were on, the address you looked up, and, on your first visit,
              the referring site and any campaign (UTM) parameters in the URL. This tells us which
              features matter and where the product falls short.
            </Li>
            <Li>
              <strong className="text-text-primary">Session replay (Microsoft Clarity).</strong>{" "}
              During our early-access period we use Microsoft Clarity to understand where the
              interface confuses people. Clarity records anonymized interactions (clicks, scrolls,
              page structure); it masks typed input by default. See{" "}
              <a
                href="https://privacy.microsoft.com/privacystatement"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-text hover:underline"
              >
                Microsoft's privacy statement
              </a>
              .
            </Li>
            <Li>
              <strong className="text-text-primary">Account details.</strong> If you sign in with
              Google, we store your name, email address, and profile picture URL. Signing in is
              optional — the Scorecard works anonymously.
            </Li>
            <Li>
              <strong className="text-text-primary">Payments.</strong> Purchases are processed by{" "}
              <a
                href="https://stripe.com/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-text hover:underline"
              >
                Stripe
              </a>
              . We never see or store your card number; we keep a record of what was purchased
              (including the parcel a report covers) so you keep access to it.
            </Li>
            <Li>
              <strong className="text-text-primary">Conversations.</strong> Chat conversations are
              saved to your account when you're signed in, so you can revisit them. Anonymous chat
              is not persisted. Shared conversation links are readable by anyone with the link
              until you revoke them.
            </Li>
            <Li>
              <strong className="text-text-primary">Error reports.</strong> We use Sentry to
              capture application errors (stack traces and request context) so we can fix bugs.
            </Li>
            <Li>
              <strong className="text-text-primary">Infrastructure logs.</strong> Cloudflare
              provides DNS, TLS, and basic traffic analytics for this site and sees requests in
              transit, as any CDN does.
            </Li>
          </ul>
        </Section>

        <Section title="What we don't do">
          <ul className="list-disc pl-5 space-y-2">
            <Li>We don't sell your personal data, and we don't share it with advertisers or data brokers.</Li>
            <Li>We don't run third-party advertising trackers.</Li>
            <Li>We don't require an account to use the free Scorecard.</Li>
            <Li>
              The property data we show (zoning, assessments, permits, sales) is public record
              published by the City of Chicago, Cook County, and federal agencies — it's about
              parcels, not about you.
            </Li>
          </ul>
        </Section>

        <Section title="Cookies">
          <P>
            We use cookies only for authentication (keeping you signed in, and a CSRF-protection
            token) and browser storage for preferences like theme and language, plus the anonymous
            analytics IDs described above. There are no advertising cookies.
          </P>
        </Section>

        <Section title="Retention & deletion">
          <P>
            You can delete your account and its conversations at any time from the Settings page.
            Purchase records are retained as required for accounting. Analytics events are kept so
            we can measure the product over time; they carry a random visitor ID, not your name.
          </P>
        </Section>

        <Section title="Where data lives">
          <P>
            The application and its database run on a server in Germany (Hetzner). Stripe, Google,
            Microsoft Clarity, Sentry, and Cloudflare process data in their own regions under
            their own policies.
          </P>
        </Section>

        <Section title="Contact">
          <P>
            Questions, or want something deleted? Email{" "}
            <a href="mailto:jack@urbanlayerchicago.com" className="text-accent-text hover:underline">
              jack@urbanlayerchicago.com
            </a>
            . This is a small product built by one person in the open — you'll get a real reply.
          </P>
        </Section>
      </article>
    </div>
  );
}
