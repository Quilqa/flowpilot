import { FUNCTION_COLOR } from "../nodeTypes.js";

// Background region behind a function body. Purely decorative: it must never
// swallow clicks meant for the nodes sitting on top of it.
export default function FunctionArea({ data }) {
  return (
    <div className="function-area"
         style={{ width: data.width, height: data.height, borderColor: FUNCTION_COLOR }}>
      <div className="function-area-title" style={{ background: FUNCTION_COLOR }}>
        ƒ {data.name}
        <span className="function-area-count">{data.nodeCount} node{data.nodeCount === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}
