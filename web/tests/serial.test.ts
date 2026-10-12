import { afterEach, expect, test, vi } from "vitest";
import { openSerial } from "../src/serial";

type Signals = { dataTerminalReady?: boolean; requestToSend?: boolean };

function fakePort(signals: Signals[]) {
  return {
    readable: new ReadableStream<Uint8Array>(),
    writable: new WritableStream<Uint8Array>(),
    open: async () => undefined,
    close: async () => undefined,
    setSignals: async (s: Signals) => {
      signals.push(s);
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("lowers RTS before DTR, so a native USB ESP32-S3 is not reset on connect", async () => {
  // Chrome applies each line on its own. DTR low while RTS is still high is the ESP32-S3
  // USB-Serial/JTAG reset request (seen on the Nano ESP32, 11 Oct 2026).
  const signals: Signals[] = [];
  const port = fakePort(signals);
  vi.stubGlobal("navigator", { serial: { requestPort: async () => port } });
  const transport = await openSerial(
    () => undefined,
    () => undefined,
  );
  expect(signals).toEqual([{ requestToSend: false }, { dataTerminalReady: false }]);
  await transport.close();
});
