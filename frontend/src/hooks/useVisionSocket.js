import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_VISION_WS_URL ?? "ws://127.0.0.1:8000/ws/vision";
const RECONNECT_DELAY_MS = 1500;

/** Same auto-reconnecting pattern as useSimulationSocket, on the separate
 * /ws/vision channel — camera frames run at a much lower rate than
 * simulation ticks, so they're kept off the main state socket entirely. */
export function useVisionSocket() {
  const [snapshot, setSnapshot] = useState(null);
  const socketRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer;

    function connect() {
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onmessage = (event) => {
        try {
          setSnapshot(JSON.parse(event.data));
        } catch {
          // ignore malformed frame
        }
      };

      socket.onclose = () => {
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => socket.close();
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socketRef.current?.close();
    };
  }, []);

  return { snapshot };
}
