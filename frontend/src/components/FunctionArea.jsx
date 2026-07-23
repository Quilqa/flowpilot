import { useRef } from "react";
import { useStore } from "reactflow";
import { FUNCTION_COLOR } from "../nodeTypes.js";

// Background region behind a function body. The box itself is inert (clicks pass
// through to the nodes on top), but its title bar is a drag handle: dragging the
// ƒ block moves every node in the function's body together.
export default function FunctionArea({ data }) {
  // Live zoom, so a screen-pixel drag translates to the right flow-space delta.
  const zoom = useStore((s) => s.transform[2]);
  const drag = useRef(null); // { lastX, lastY } in screen px

  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    // Stop React Flow from also panning the canvas. stopPropagation alone is
    // not enough — RF's pan is a d3-zoom listener on an ancestor — so the
    // handle also carries the `nopan` class, which RF's pan filter excludes.
    e.stopPropagation();
    e.preventDefault();
    drag.current = { lastX: e.clientX, lastY: e.clientY };
    data.onBodyDragStart?.();          // one undo step for the whole move
    // Capture so moves keep coming even if the cursor leaves the handle; best
    // effort (a synthetic pointer has nothing to capture).
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch {}
  };

  const onPointerMove = (e) => {
    if (!drag.current) return;
    e.stopPropagation();
    const z = zoom || 1;
    const dx = (e.clientX - drag.current.lastX) / z;
    const dy = (e.clientY - drag.current.lastY) / z;
    drag.current.lastX = e.clientX;
    drag.current.lastY = e.clientY;
    if (dx || dy) data.onBodyTranslate?.(data.memberIds, dx, dy);
  };

  const endDrag = (e) => {
    if (!drag.current) return;
    e.stopPropagation();
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch {}
    drag.current = null;
  };

  return (
    <div className="function-area"
         style={{ width: data.width, height: data.height, borderColor: FUNCTION_COLOR }}>
      <div className="function-area-title nopan" title="Drag to move the whole function"
           style={{ background: FUNCTION_COLOR }}
           onPointerDown={onPointerDown} onPointerMove={onPointerMove}
           onPointerUp={endDrag} onPointerCancel={endDrag}>
        ƒ {data.name}
        <span className="function-area-count">{data.nodeCount} node{data.nodeCount === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}
