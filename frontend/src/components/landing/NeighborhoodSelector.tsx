import { useCallback, useEffect, useRef, useState } from "react";
import { COMMUNITY_AREA_LIST } from "../../lib/communityAreas";
import { getAutocomplete, getCommunityAreaByPoint } from "../../lib/api";
import type { AddressSuggestion } from "../../lib/types";

interface Props {
  onSelect: (communityArea: number, name: string) => void;
  loading: boolean;
}

export function NeighborhoodSelector({ onSelect, loading }: Props) {
  // Neighborhood dropdown state
  const [query, setQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Address autocomplete state
  const [addressQuery, setAddressQuery] = useState("");
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [addressOpen, setAddressOpen] = useState(false);
  const [addressHighlight, setAddressHighlight] = useState(0);
  const [resolving, setResolving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const addressRef = useRef<HTMLDivElement>(null);

  const filtered = query.trim()
    ? COMMUNITY_AREA_LIST.filter((ca) =>
        ca.name.toLowerCase().includes(query.toLowerCase()),
      )
    : COMMUNITY_AREA_LIST;

  useEffect(() => {
    setHighlightIndex(0);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (addressRef.current && !addressRef.current.contains(e.target as Node)) {
        setAddressOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleNeighborhoodKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[highlightIndex]) {
      e.preventDefault();
      selectNeighborhood(filtered[highlightIndex]);
    } else if (e.key === "Escape") {
      setDropdownOpen(false);
    }
  }

  function selectNeighborhood(ca: { id: number; name: string }) {
    setQuery(ca.name);
    setDropdownOpen(false);
    setAddressQuery("");
    setSuggestions([]);
    onSelect(ca.id, ca.name);
  }

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 3) { setSuggestions([]); return; }
    const results = await getAutocomplete(q);
    setSuggestions(results);
    setAddressOpen(results.length > 0);
    setAddressHighlight(0);
  }, []);

  function handleAddressChange(val: string) {
    setAddressQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), 300);
  }

  async function selectAddress(s: AddressSuggestion) {
    setAddressQuery(s.address);
    setAddressOpen(false);
    setQuery("");
    setResolving(true);
    const result = await getCommunityAreaByPoint(s.lat, s.lon);
    setResolving(false);
    if (result) {
      onSelect(result.community_area, result.name);
    }
  }

  function handleAddressKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAddressHighlight((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAddressHighlight((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && suggestions[addressHighlight]) {
      e.preventDefault();
      selectAddress(suggestions[addressHighlight]);
    } else if (e.key === "Escape") {
      setAddressOpen(false);
    }
  }

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3 max-w-2xl mx-auto">
      {/* Neighborhood dropdown */}
      <div ref={dropdownRef} className="relative w-full sm:w-64">
        <label className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
          Neighborhood
        </label>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setDropdownOpen(true); }}
          onFocus={() => setDropdownOpen(true)}
          onKeyDown={handleNeighborhoodKey}
          placeholder="Search areas..."
          className="w-full bg-dark-elevated border border-dark-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors"
        />
        {dropdownOpen && filtered.length > 0 && (
          <ul className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-dark-surface border border-dark-border rounded-lg shadow-xl">
            {filtered.map((ca, i) => (
              <li
                key={ca.id}
                onClick={() => selectNeighborhood(ca)}
                onMouseEnter={() => setHighlightIndex(i)}
                className={`px-3 py-2 text-sm cursor-pointer transition-colors ${
                  i === highlightIndex
                    ? "bg-accent/20 text-white"
                    : "text-text-secondary hover:bg-dark-elevated hover:text-white"
                }`}
              >
                {ca.name}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Divider */}
      <div className="hidden sm:flex items-center pb-2">
        <span className="text-text-muted text-xs">or</span>
      </div>

      {/* Address autocomplete */}
      <div ref={addressRef} className="relative w-full sm:w-72">
        <label className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
          Address
        </label>
        <input
          type="text"
          value={addressQuery}
          onChange={(e) => handleAddressChange(e.target.value)}
          onKeyDown={handleAddressKey}
          placeholder="Enter an address..."
          className="w-full bg-dark-elevated border border-dark-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors"
        />
        {addressOpen && suggestions.length > 0 && (
          <ul className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-dark-surface border border-dark-border rounded-lg shadow-xl">
            {suggestions.map((s, i) => (
              <li
                key={s.address}
                onClick={() => selectAddress(s)}
                onMouseEnter={() => setAddressHighlight(i)}
                className={`px-3 py-2 text-sm cursor-pointer transition-colors ${
                  i === addressHighlight
                    ? "bg-accent/20 text-white"
                    : "text-text-secondary hover:bg-dark-elevated hover:text-white"
                }`}
              >
                {s.address}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Loading spinner */}
      {(loading || resolving) && (
        <div className="flex items-center pb-2">
          <div className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}
