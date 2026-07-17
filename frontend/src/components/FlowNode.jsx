import { Handle, Position } from "reactflow";
import { NODE_DEFS } from "../nodeTypes.js";

// Custom node renderer. `data.nodeType` selects styling and handles.
export default function FlowNode({ data, selected }) {
  const def = NODE_DEFS[data.nodeType] || { label: data.nodeType, color: "#64748b", ports: "linear" };
  const ports = def.ports;

  return (
    <div className={`fnode ${selected ? "selected" : ""} ${data.active ? "active" : ""}`}
         style={{ borderColor: def.color }}>
      {ports !== "start" && <Handle type="target" position={Position.Left} className="handle" />}

      <div className="fnode-header" style={{ background: def.color }}>
        {def.label}
      </div>
      {data.summary && <div className="fnode-body">{data.summary}</div>}

      {ports === "linear" && <Handle type="source" position={Position.Right} className="handle" />}
      {ports === "start" && <Handle type="source" position={Position.Right} className="handle" />}
      {ports === "condition" && (
        <>
          <Handle id="yes" type="source" position={Position.Right} style={{ top: "35%" }}
                  className="handle handle-yes" />
          <Handle id="no" type="source" position={Position.Right} style={{ top: "70%" }}
                  className="handle handle-no" />
          <span className="port-label yes">Yes</span>
          <span className="port-label no">No</span>
        </>
      )}
      {/* 'in' (End node) has no source handle */}
    </div>
  );
}
