interface LayerConfig {
  id: string;
  label: string;
  color: string;
  active: boolean;
}

interface Props {
  layers: LayerConfig[];
  onToggle: (id: string) => void;
}

export function MapLayerToggles({ layers, onToggle }: Props) {
  return (
    <div className="absolute top-2 right-2 z-10 flex flex-col gap-1">
      {layers.map((layer) => (
        <button
          key={layer.id}
          onClick={() => onToggle(layer.id)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium
            transition-all duration-150 backdrop-blur-sm border
            ${
              layer.active
                ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60 hover:text-text-secondary"
            }`}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              backgroundColor: layer.active ? layer.color : "#555",
            }}
          />
          {layer.label}
        </button>
      ))}
    </div>
  );
}
