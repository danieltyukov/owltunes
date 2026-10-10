// Web Serial transport. The DOM library has no Web Serial types yet, so the few used are declared here.

import type { Transport } from "./protocol";

interface SerialPortLike {
  readonly readable: ReadableStream<Uint8Array> | null;
  readonly writable: WritableStream<Uint8Array> | null;
  open(options: { baudRate: number }): Promise<void>;
  close(): Promise<void>;
  setSignals?(signals: { dataTerminalReady?: boolean; requestToSend?: boolean }): Promise<void>;
}

interface SerialLike {
  requestPort(): Promise<SerialPortLike>;
}

function serial(): SerialLike | undefined {
  return (navigator as Navigator & { serial?: SerialLike }).serial;
}

export function serialSupported(): boolean {
  return serial() !== undefined;
}

/** Let the person pick the owl's port, open it, and pass everything it sends to onData. */
export async function openSerial(onData: (chunk: Uint8Array) => void, onClose: () => void): Promise<Transport> {
  const api = serial();
  if (api === undefined) {
    throw new Error("Web Serial is not available");
  }
  const port = await api.requestPort();
  await port.open({ baudRate: 115200 });
  // Keep DTR and RTS low: on boards with an auto-reset circuit, moving them resets the ESP32.
  await port.setSignals?.({ dataTerminalReady: false, requestToSend: false });
  if (port.readable === null || port.writable === null) {
    throw new Error("the port opened without streams");
  }
  const reader = port.readable.getReader();
  const writer = port.writable.getWriter();
  const encoder = new TextEncoder();
  void (async () => {
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        onData(value);
      }
    } catch {
      // The cable came out or the port was closed; onClose reports it.
    } finally {
      reader.releaseLock();
      onClose();
    }
  })();
  return {
    write: (text) => writer.write(encoder.encode(text)),
    close: async () => {
      await reader.cancel().catch(() => undefined);
      writer.releaseLock();
      await port.close().catch(() => undefined);
    },
  };
}
