import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="bg-dark-surface border-t border-dark-border">
      <div className="max-w-5xl mx-auto py-12 px-6 grid grid-cols-1 md:grid-cols-3 gap-10 text-sm">
        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">UrbanLayer</h4>
          <p className="text-text-secondary leading-relaxed">
            Chicago public data, explored through conversation.
          </p>
          <p className="text-text-muted text-xs">&copy; 2026 UrbanLayer</p>
        </div>

        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">Data Sources</h4>
          <ul className="space-y-2 text-text-secondary text-xs">
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">City of Chicago</span>
              <span className="text-text-muted"> — Crime, 311, Permits, Violations, Business Licenses, </span>
              <a href="https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors text-text-secondary">
                Zoning MapServer
              </a>
              <span className="text-text-muted"> (12 overlay layers)</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">Cook County</span>
              <span className="text-text-muted"> — Property Characteristics, Assessed Values, Sales History, Tax Estimation</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">Federal & External</span>
              <span className="text-text-muted"> — Census Demographics, FEMA Flood Zones, EPA Brownfields, Walk Score</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">Legal</span>
              <span className="text-text-muted"> — Chicago Municipal Code (14,535 sections)</span>
            </li>
          </ul>
        </div>

        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">About</h4>
          <ul className="space-y-2 text-text-secondary">
            <li>
              <Link to="/about" className="hover:text-accent transition-colors">
                How it works
              </Link>
            </li>
            <li className="text-text-muted text-xs">Not affiliated with the City of Chicago</li>
            <li className="text-text-muted text-xs">Data may be delayed up to 7 days</li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
