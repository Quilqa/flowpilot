import { PALETTE } from "../nodeTypes.js";

// Grouped node palette. Drag onto canvas or click to add near center.
export default function NodePalette({ onAdd }) {
  return (
    <div className="palette">
      <div className="palette-title">Nodes</div>
      {PALETTE.map((grp) => (
        <div className="palette-group" key={grp.group}>
          <div className="palette-group-title">{grp.group}</div>
          {grp.items.map((it) => (
            <div
              key={it.type}
              className="palette-item"
              style={{ borderLeftColor: it.color }}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData("application/flowpilot", it.type);
                e.dataTransfer.effectAllowed = "move";
              }}
              onClick={() => onAdd(it.type)}
              title="Drag to canvas or click to add"
            >
              {it.label}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
