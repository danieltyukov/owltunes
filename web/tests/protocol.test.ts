import { afterEach, describe, expect, test, vi } from "vitest";
import { decodeLine, encodeRequest, LINE_MAX, LineSplitter, OwlClient, OwlError, type Transport } from "../src/protocol";

const bytes = (s: string): Uint8Array => new TextEncoder().encode(s);

class FakeTransport implements Transport {
  written: string[] = [];
  closes = 0;
  write(text: string): Promise<void> {
    this.written.push(text);
    return Promise.resolve();
  }
  close(): Promise<void> {
    this.closes++;
    return Promise.resolve();
  }
}

describe("encodeRequest", () => {
  test("writes one compact prefixed line", () => {
    expect(encodeRequest(3, "wifi_add", { ssid: "Home", password: "password1" })).toBe(
      '@owl {"id":3,"cmd":"wifi_add","ssid":"Home","password":"password1"}\n',
    );
  });

  test("fits the longest Spotify code the owl takes in one line", () => {
    const state = `${"Q".repeat(22)}.192.168.123.234`;
    expect(() => encodeRequest(2147483647, "spotify_code", { code: "A".repeat(1023), state })).not.toThrow();
  });

  test("refuses lines over the limit", () => {
    expect(() => encodeRequest(1, "spotify_code", { code: "x".repeat(LINE_MAX) })).toThrow(OwlError);
  });
});

describe("decodeLine", () => {
  test("reads replies and events", () => {
    expect(decodeLine('@owl {"id":1,"ok":true,"name":"OwlTunes-1A2B"}')).toEqual({ id: 1, ok: true, name: "OwlTunes-1A2B" });
    expect(decodeLine('@owl {"event":"spotify","state":"linked"}')).toEqual({ event: "spotify", state: "linked" });
  });

  test("ignores logs, noise and echoed requests", () => {
    expect(decodeLine("I (812) wifi: connected")).toBeNull();
    expect(decodeLine("@owl {broken")).toBeNull();
    expect(decodeLine("@owl [1,2]")).toBeNull();
    expect(decodeLine('@owl {"id":1,"cmd":"hello"}')).toBeNull();
  });
});

describe("LineSplitter", () => {
  test("LineSplitter reassembles chunks", () => {
    const lines: string[] = [];
    const splitter = new LineSplitter((line) => lines.push(line));
    splitter.push(bytes('@owl {"id"'));
    splitter.push(bytes(':1,"ok":true}\r\nI (5) log\n@owl {"ev'));
    expect(lines).toEqual(['@owl {"id":1,"ok":true}', "I (5) log"]);
    splitter.push(bytes('ent":"network","state":"up"}\n'));
    expect(lines[2]).toBe('@owl {"event":"network","state":"up"}');
  });

  test("ends a line at a bare CR, CR LF or CR LF split across chunks", () => {
    const lines: string[] = [];
    const splitter = new LineSplitter((line) => lines.push(line));
    splitter.pushText("info\rhelp\r\nthird\r");
    splitter.pushText("\nfourth\n");
    expect(lines).toEqual(["info", "help", "third", "fourth"]);
  });

  test("keeps multi-byte characters split across chunks", () => {
    const lines: string[] = [];
    const splitter = new LineSplitter((line) => lines.push(line));
    const all = bytes("Caf\u00e9\n");
    splitter.push(all.slice(0, 4));
    splitter.push(all.slice(4));
    expect(lines).toEqual(["Caf\u00e9"]);
  });

  test("drops an over-long line whole and carries on", () => {
    const lines: string[] = [];
    const splitter = new LineSplitter((line) => lines.push(line));
    splitter.pushText("x".repeat(LINE_MAX + 1));
    splitter.pushText("tail\n@owl {}\n");
    expect(lines).toEqual(["@owl {}"]);
  });
});

describe("OwlClient", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test("matches replies to requests by id", async () => {
    const transport = new FakeTransport();
    const client = new OwlClient(transport);
    const first = client.request("hello");
    const second = client.request("spotify_begin");
    expect(transport.written).toEqual(['@owl {"id":1,"cmd":"hello"}\n', '@owl {"id":2,"cmd":"spotify_begin"}\n']);
    client.receive(bytes('@owl {"id":2,"ok":true,"authorize_url":"https://accounts.spotify.com/authorize?x"}\n'));
    client.receive(bytes('@owl {"id":1,"ok":true,"setup":"needs_wifi"}\n'));
    await expect(first).resolves.toMatchObject({ setup: "needs_wifi" });
    await expect(second).resolves.toMatchObject({ authorize_url: "https://accounts.spotify.com/authorize?x" });
  });

  test("rejects with the owl's error code", async () => {
    const client = new OwlClient(new FakeTransport());
    const reply = client.request("spotify_client", { client_id: "abc" });
    client.receive(bytes('@owl {"id":1,"ok":false,"error":"bad_client_id"}\n'));
    await expect(reply).rejects.toMatchObject({ code: "bad_client_id", cmd: "spotify_client" });
  });

  test("times out when the owl stays silent", async () => {
    vi.useFakeTimers();
    const client = new OwlClient(new FakeTransport(), 1000);
    const reply = client.request("hello");
    vi.advanceTimersByTime(1001);
    await expect(reply).rejects.toMatchObject({ code: "timeout" });
  });

  test("passes events to listeners until they unsubscribe", () => {
    const client = new OwlClient(new FakeTransport());
    const seen: string[] = [];
    const stop = client.onEvent((e) => seen.push(`${e.event}:${e.state}`));
    client.receive(bytes('@owl {"event":"spotify","state":"linking"}\n'));
    stop();
    client.receive(bytes('@owl {"event":"spotify","state":"linked"}\n'));
    expect(seen).toEqual(["spotify:linking"]);
  });

  test("close fails waiting requests", async () => {
    const client = new OwlClient(new FakeTransport());
    const reply = client.request("hello");
    client.close();
    await expect(reply).rejects.toMatchObject({ code: "disconnected" });
  });

  test("close closes the transport once and refuses new requests", async () => {
    const transport = new FakeTransport();
    const client = new OwlClient(transport);
    client.close();
    client.close();
    expect(transport.closes).toBe(1);
    await expect(client.request("hello")).rejects.toMatchObject({ code: "disconnected" });
    expect(transport.written).toEqual([]);
  });
});
