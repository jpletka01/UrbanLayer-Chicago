import { FilterButton } from "./FilterButton";

export interface ToggleOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  options: ToggleOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * A single-select group of pill toggles (arrest / 311 status / permit cost
 * filters on the sidebar map). Built on {@link FilterButton}.
 */
export function ToggleGroup<T extends string>({ options, value, onChange }: Props<T>) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map((opt) => (
        <FilterButton key={opt.value} active={value === opt.value} onClick={() => onChange(opt.value)}>
          {opt.label}
        </FilterButton>
      ))}
    </div>
  );
}
