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
          <ul className="space-y-2 text-text-secondary">
            <li>
              <a href="https://data.cityofchicago.org" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">
                Chicago Data Portal
              </a>
              <span className="text-text-muted"> — Crime, 311, Permits</span>
            </li>
            <li>
              <a href="https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">
                Chicago Zoning Map
              </a>
            </li>
            <li>
              <span className="text-text-secondary">Chicago Municipal Code</span>
              <span className="text-text-muted"> — 14,000+ sections indexed</span>
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
            <li className="text-text-muted">Not affiliated with the City of Chicago</li>
            <li className="text-text-muted">Data may be delayed up to 7 days</li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
