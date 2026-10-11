// The @owl line protocol, mirrored from firmware/components/provisioning (docs/provisioning-protocol.md).

export const PREFIX = "@owl ";
export const LINE_MAX = 1536;

export type Params = Record<string, unknown>;

export interface OwlReply {
  id: number;
  ok: boolean;
  error?: string;
  [key: string]: unknown;
}

export interface OwlEvent {
  event: string;
  state: string;
  [key: string]: unknown;
}

export class OwlError extends Error {
  constructor(
    readonly code: string,
    readonly cmd: string,
  ) {
    super(`${cmd}: ${code}`);
    this.name = "OwlError";
  }
}

const encoder = new TextEncoder();

export function encodeRequest(id: number, cmd: string, params: Params = {}): string {
  const line = `${PREFIX}${JSON.stringify({ id, cmd, ...params })}\n`;
  if (encoder.encode(line).length > LINE_MAX) {
    throw new OwlError("too_long", cmd);
  }
  return line;
}

/** Parse one console line. Anything that is not an @owl JSON object (logs, noise) gives null. */
export function decodeLine(line: string): OwlReply | OwlEvent | null {
  if (!line.startsWith(PREFIX)) {
    return null;
  }
  try {
    const msg: unknown = JSON.parse(line.slice(PREFIX.length));
    if (typeof msg !== "object" || msg === null || Array.isArray(msg)) {
      return null;
    }
    const obj = msg as Record<string, unknown>;
    if (typeof obj.event === "string" && typeof obj.state === "string") {
      return obj as OwlEvent;
    }
    if (typeof obj.id === "number" && typeof obj.ok === "boolean") {
      return obj as OwlReply;
    }
    return null;
  } catch {
    return null;
  }
}

/** Reassembles a byte stream into lines; over-long lines are dropped whole. A line ends at "\n", "\r" or "\r\n" (the
 * LF of a CR LF pair, even in the next chunk, only makes an empty line, which is skipped), like the owl. */
export class LineSplitter {
  private buffer = "";
  private discarding = false;
  private readonly decoder = new TextDecoder();

  constructor(private readonly onLine: (line: string) => void) {}

  push(chunk: Uint8Array): void {
    this.pushText(this.decoder.decode(chunk, { stream: true }));
  }

  pushText(text: string): void {
    const parts = text.split(/[\r\n]/);
    parts.forEach((part, i) => {
      if (!this.discarding) {
        this.buffer += part;
        if (this.buffer.length > LINE_MAX) {
          this.buffer = "";
          this.discarding = true;
        }
      }
      if (i < parts.length - 1) {
        if (!this.discarding && this.buffer.length > 0) {
          this.onLine(this.buffer);
        }
        this.buffer = "";
        this.discarding = false;
      }
    });
  }
}

/** Something that carries text to the owl: Web Serial now, Web Bluetooth in P3. */
export interface Transport {
  write(text: string): Promise<void>;
  close(): Promise<void>;
}

interface Pending {
  cmd: string;
  resolve: (reply: OwlReply) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

/** Matches replies to requests by id and hands events to listeners. Feed it with receive(). */
export class OwlClient {
  private nextId = 1;
  private closed = false;
  private readonly pending = new Map<number, Pending>();
  private readonly listeners = new Set<(event: OwlEvent) => void>();
  private readonly splitter = new LineSplitter((line) => this.onLine(line));

  constructor(
    private readonly transport: Transport,
    private readonly timeoutMs = 5000,
  ) {}

  receive(chunk: Uint8Array): void {
    this.splitter.push(chunk);
  }

  /** Send a command; resolves with the reply, rejects with OwlError when ok is false or on timeout. */
  request(cmd: string, params: Params = {}): Promise<OwlReply> {
    if (this.closed) {
      return Promise.reject(new OwlError("disconnected", cmd));
    }
    const id = this.nextId++;
    let line: string;
    try {
      line = encodeRequest(id, cmd, params);
    } catch (err) {
      return Promise.reject(err as Error);
    }
    return new Promise<OwlReply>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new OwlError("timeout", cmd));
      }, this.timeoutMs);
      this.pending.set(id, { cmd, resolve, reject, timer });
      this.transport.write(line).catch((err: unknown) => {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(err instanceof Error ? err : new OwlError("write_failed", cmd));
      });
    });
  }

  onEvent(listener: (event: OwlEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * The one owner of the connection: fail every request still waiting, refuse new ones and close the
   * transport. Safe to call more than once.
   */
  close(code = "disconnected"): void {
    if (!this.closed) {
      this.closed = true;
      this.transport.close().catch(() => undefined);
    }
    for (const [id, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new OwlError(code, p.cmd));
      this.pending.delete(id);
    }
  }

  private onLine(line: string): void {
    const msg = decodeLine(line);
    if (msg === null) {
      return;
    }
    if ("event" in msg) {
      for (const listener of this.listeners) {
        listener(msg as OwlEvent);
      }
      return;
    }
    const reply = msg as OwlReply;
    const p = this.pending.get(reply.id);
    if (p === undefined) {
      return;
    }
    clearTimeout(p.timer);
    this.pending.delete(reply.id);
    if (reply.ok) {
      p.resolve(reply);
    } else {
      p.reject(new OwlError(typeof reply.error === "string" ? reply.error : "unknown", p.cmd));
    }
  }
}
