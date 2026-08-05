import { useEffect, useRef, useState } from "react";

// 127.0.0.1, not "localhost" — on Windows, "localhost" can resolve to the
// IPv6 loopback (::1) while uvicorn only binds IPv4, which silently kills
// the WebSocket handshake with no error on the server side.
const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8000/ws/simulation";
const RECONNECT_DELAY_MS = 1500;

/**
 * Connects to the simulation WebSocket and keeps the latest intersection
 * snapshot in state. Reconnects automatically if the backend restarts.
 */
export function useSimulationSocket() {
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer;

    function connect() {
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);

      socket.onmessage = (event) => {
        try {
          setSnapshot(JSON.parse(event.data));
        } catch {
          // ignore malformed frame
        }
      };

      socket.onclose = () => {
        setConnected(false);
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

  return { snapshot, connected };
}
