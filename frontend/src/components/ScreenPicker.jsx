import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Full-window overlay that captures a fresh screenshot and lets the user pick
// a point (with zoom lens) or drag a region. Coordinates map back to native
// screen pixels via the natural/displayed size ratio.
export default function ScreenPicker({ mode, onPick, onCancel }) {
  const [src, setSrc] = useState(null);
  const [nat, setNat] = useState({ w: 0, h: 0 });
  const [hover, setHover] = useState(null); // {sx,sy screen px, cx,cy client px}
  const [drag, setDrag] = useState(null); // {x0,y0,x1,y1} in client px
  const imgRef = useRef(null);

  useEffect(() => {
    const url = api.screenshotUrl();
    setSrc(url);
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const toScreen = (clientX, clientY) => {
    const img = imgRef.current;
    if (!img || !nat.w) return { x: 0, y: 0 };
    const r = img.getBoundingClientRect();
    // The image is rendered with object-fit: contain, so it occupies a
    // centered, aspect-preserved rectangle inside the element box (letterbox
    // bars fill the rest). Map clicks against that content rect, not the box.
    const scale = Math.min(r.width / nat.w, r.height / nat.h);
    const contentW = nat.w * scale;
    const contentH = nat.h * scale;
    const offX = (r.width - contentW) / 2;
    const offY = (r.height - contentH) / 2;
    const sx = Math.round((clientX - r.left - offX) / scale);
    const sy = Math.round((clientY - r.top - offY) / scale);
    return { x: Math.max(0, Math.min(nat.w - 1, sx)), y: Math.max(0, Math.min(nat.h - 1, sy)) };
  };

  const onMove = (e) => {
    const s = toScreen(e.clientX, e.clientY);
    setHover({ ...s, cx: e.clientX, cy: e.clientY });
    if (drag) setDrag({ ...drag, x1: e.clientX, y1: e.clientY });
  };

  const onDown = (e) => {
    if (mode === "region") setDrag({ x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY });
  };

  const onUp = (e) => {
    if (mode === "point") {
      onPick(toScreen(e.clientX, e.clientY));
      return;
    }
    if (drag) {
      const a = toScreen(Math.min(drag.x0, drag.x1), Math.min(drag.y0, drag.y1));
      const b = toScreen(Math.max(drag.x0, drag.x1), Math.max(drag.y0, drag.y1));
      const region = { left: a.x, top: a.y, width: b.x - a.x, height: b.y - a.y };
      if (region.width > 3 && region.height > 3) onPick(region);
      else setDrag(null);
    }
  };

  const dragRect = drag && {
    left: Math.min(drag.x0, drag.x1), top: Math.min(drag.y0, drag.y1),
    width: Math.abs(drag.x1 - drag.x0), height: Math.abs(drag.y1 - drag.y0),
  };

  return (
    <div className="picker-overlay" onMouseMove={onMove} onMouseDown={onDown} onMouseUp={onUp}>
      <div className="picker-bar">
        <span>{mode === "point" ? "Click the exact pixel" : "Drag to select a region"}</span>
        {hover && <span className="mono">screen: {hover.x}, {hover.y}</span>}
        <button className="btn small" onMouseUp={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onCancel(); }}>Cancel (Esc)</button>
      </div>
      {src && (
        <img ref={imgRef} className="picker-img" src={src} alt="screen"
             draggable={false}
             onLoad={(e) => setNat({ w: e.target.naturalWidth, h: e.target.naturalHeight })} />
      )}
      {mode === "region" && dragRect && (
        <div className="picker-rect" style={{
          left: dragRect.left, top: dragRect.top, width: dragRect.width, height: dragRect.height,
        }} />
      )}
      {mode === "point" && hover && src && (
        <ZoomLens src={src} nat={nat} sx={hover.x} sy={hover.y} cx={hover.cx} cy={hover.cy} />
      )}
    </div>
  );
}

// Magnified area around the cursor for pixel-accurate picking.
function ZoomLens({ src, nat, sx, sy, cx, cy }) {
  const LENS = 140, ZOOM = 6;
  const bgW = nat.w * ZOOM, bgH = nat.h * ZOOM;
  const posX = -(sx * ZOOM - LENS / 2);
  const posY = -(sy * ZOOM - LENS / 2);
  const left = Math.min(cx + 20, window.innerWidth - LENS - 10);
  const top = Math.min(cy + 20, window.innerHeight - LENS - 10);
  return (
    <div className="zoom-lens" style={{
      left, top, width: LENS, height: LENS,
      backgroundImage: `url(${src})`,
      backgroundSize: `${bgW}px ${bgH}px`,
      backgroundPosition: `${posX}px ${posY}px`,
    }}>
      <div className="zoom-cross-v" /><div className="zoom-cross-h" />
    </div>
  );
}
