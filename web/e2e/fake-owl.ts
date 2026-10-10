// A simulated owl behind a fake navigator.serial, so the real page code runs against the protocol.
// installFakeOwl runs inside the browser (page.addInitScript), so it must not use anything from
// this module's scope.

export interface FakeOwlOptions {
  exchange: "linked" | "failed";
  ip: string;
  /** Start with the owl ignoring every request, like firmware that does not know the protocol. */
  silent?: boolean;
  /** The error a failed exchange reports; an empty string sends the event without one. */
  failError?: string;
  /** A client ID and redirect URI the owl already holds, as if saved from another copy of the site. */
  savedClientId?: string;
  savedRedirectUri?: string;
}

export interface FakeOwlState {
  networks: { ssid: string; password: string }[];
  clientId: string;
  redirectUri: string;
  linked: boolean;
  state: string | null;
  codes: string[];
  silent: boolean;
  opens: number;
}

export function installFakeOwl(options: FakeOwlOptions): void {
  const owl: FakeOwlState = { networks: [], clientId: options.savedClientId ?? "", redirectUri: options.savedRedirectUri ?? "", linked: false, state: null, codes: [], silent: options.silent === true, opens: 0 };
  (window as unknown as { __owl: FakeOwlState }).__owl = owl;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  let output: ReadableStreamDefaultController<Uint8Array> | null = null;
  let input = "";
  const send = (text: string): void => output?.enqueue(encoder.encode(`${text}\n`));
  const reply = (id: unknown, fields: Record<string, unknown>): void => send(`@owl ${JSON.stringify({ id, ...fields })}`);
  const event = (fields: Record<string, unknown>): void => send(`@owl ${JSON.stringify(fields)}`);
  (window as unknown as { __owlEmit: (e: Record<string, unknown>) => void }).__owlEmit = event;
  const online = (): boolean => owl.networks.length > 0;
  const later = (fn: () => void, ms = 30): void => void setTimeout(fn, ms);

  const handle = (req: Record<string, unknown>): void => {
    if (owl.silent) {
      return;
    }
    const id = req.id;
    const str = (key: string): string => (typeof req[key] === "string" ? (req[key] as string) : "");
    switch (req.cmd) {
      case "hello":
        reply(id, {
          ok: true,
          name: "OwlTunes-1A2B",
          fw: "0.2.0",
          protocol: 1,
          setup: owl.linked ? "ready" : online() ? "needs_spotify" : "needs_wifi",
          linked: owl.linked,
          client_id: owl.clientId,
          redirect_uri: owl.redirectUri,
          ip: online() ? options.ip : "",
          networks: owl.networks.map((n) => n.ssid),
        });
        return;
      case "wifi_add": {
        const ssid = str("ssid");
        const password = str("password");
        if (ssid.length < 1 || ssid.length > 32) {
          reply(id, { ok: false, error: "bad_ssid" });
        } else if (password.length !== 0 && (password.length < 8 || password.length > 64)) {
          reply(id, { ok: false, error: "bad_password" });
        } else {
          owl.networks = owl.networks.filter((n) => n.ssid !== ssid).concat({ ssid, password });
          reply(id, { ok: true });
          later(() => event({ event: "network", state: "up", ip: options.ip }));
        }
        return;
      }
      case "wifi_remove":
        owl.networks = owl.networks.filter((n) => n.ssid !== str("ssid"));
        reply(id, { ok: true });
        return;
      case "spotify_client":
        if (!/^[0-9a-f]{32}$/.test(str("client_id"))) {
          reply(id, { ok: false, error: "bad_client_id" });
          return;
        }
        owl.clientId = str("client_id");
        owl.redirectUri = str("redirect_uri");
        reply(id, { ok: true });
        return;
      case "spotify_begin": {
        if (owl.clientId === "") {
          reply(id, { ok: false, error: "no_client_id" });
          return;
        }
        owl.state = `QEFCQ0RFRkdISUpLTE1OTw.${options.ip}`;
        const query = new URLSearchParams({
          client_id: owl.clientId,
          response_type: "code",
          redirect_uri: owl.redirectUri,
          code_challenge_method: "S256",
          code_challenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
          state: owl.state,
          scope: "user-read-playback-state user-modify-playback-state",
        });
        reply(id, { ok: true, authorize_url: `https://accounts.spotify.com/authorize?${query.toString()}` });
        return;
      }
      case "spotify_code":
        if (owl.state === null) {
          reply(id, { ok: false, error: "no_session" });
        } else if (str("state") !== owl.state) {
          reply(id, { ok: false, error: "bad_state" });
        } else {
          owl.codes.push(str("code"));
          owl.state = null;
          reply(id, { ok: true, accepted: true });
          later(() => event({ event: "spotify", state: "linking" }));
          later(() => {
            owl.linked = options.exchange === "linked";
            event(
              owl.linked
                ? { event: "spotify", state: "linked" }
                : {
                    event: "spotify",
                    state: "failed",
                    ...(options.failError === "" ? {} : { error: options.failError ?? "invalid_client" }),
                  },
            );
          }, 120);
        }
        return;
      default:
        reply(id, { ok: false, error: "unknown_cmd" });
    }
  };

  // Like a real port: open() fails while it is already open, and every open gets fresh streams.
  let isOpen = false;
  const port: Record<string, unknown> = {
    readable: null,
    writable: null,
    open: async (): Promise<void> => {
      if (isOpen) {
        throw new DOMException("The port is already open.", "InvalidStateError");
      }
      isOpen = true;
      owl.opens++;
      input = "";
      port.readable = new ReadableStream<Uint8Array>({
        start(controller) {
          output = controller;
        },
      });
      port.writable = new WritableStream<Uint8Array>({
        write(chunk) {
          input += decoder.decode(chunk, { stream: true });
          for (let end = input.indexOf("\n"); end >= 0; end = input.indexOf("\n")) {
            const line = input.slice(0, end);
            input = input.slice(end + 1);
            if (line.startsWith("@owl ")) {
              handle(JSON.parse(line.slice(5)) as Record<string, unknown>);
            }
          }
        },
      });
      later(() => send("I (412) owltunes: OWL_BOOT_OK track=\"demo\" name=OwlTunes-1A2B"), 0);
    },
    close: async (): Promise<void> => {
      isOpen = false;
    },
    setSignals: async (): Promise<void> => undefined,
  };
  Object.defineProperty(navigator, "serial", {
    configurable: true,
    value: { requestPort: async () => port },
  });
}
