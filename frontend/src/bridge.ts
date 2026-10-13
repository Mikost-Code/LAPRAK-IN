export type Fact = {
  type: string;
  value: string;
  source: string;
  reviewed: boolean;
};
export type Step = {
  unknown?: string[];
  id: string;
  title: string;
  notes: string;
  narrative: string;
  facts: Fact[];
  result: string;
  reviewed: boolean;
  checks: boolean[];
  instruction_ids: string[];
  not_applicable: string;
  revision: number;
};
export type ModuleDraft = {
  objectives: string[];
  theory: string;
  tools: string[];
  instructions: { description: string; page: number; evidence: string }[];
  unknown_pages: number[];
};
export type Project = {
  path: string;
  identity: Record<string, string>;
  revision: number;
  steps: Step[];
  images: { id: string; step_id: string; name: string; url: string }[];
  module: {
    name?: string;
    pages?: { page: number; text: string; needs_vision: boolean }[];
  };
  moduleDraft: Partial<ModuleDraft>;
  modulePending: Partial<ModuleDraft>;
  moduleReviewed: boolean;
  moduleManual: string;
  instructions: { id: string; description: string; page: number }[];
  folder: string;
  blockers: string[];
  sections: Record<string, string>;
  sectionsReviewed: boolean;
  sectionDrafts: Record<string, string>;
  build: { revision?: number };
  pdfUrl: string;
  revisions: Record<
    string,
    { created: string; data: Partial<Step> & { origin?: string } }[]
  >;
  jobs: {
    id: string;
    kind: string;
    status: string;
    error: string;
    attempts: number;
    step_id: string;
  }[];
};
export type State = {
  settings: Record<string, string | number | boolean | null>;
  compilerReady: boolean;
  aiTested: { text?: boolean; vision?: boolean };
  recent: { path: string; name: string }[];
  active: string;
  busy: string[];
  operation: string;
  setupStatus: string;
  watching: boolean;
  project: Project | null;
};
type QtSignal = { connect: (handler: (value: string) => void) => void };
type NativeBridge = {
  request: (value: string) => void;
  response: QtSignal;
  changed: QtSignal;
  notice: QtSignal;
};
declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (
      transport: unknown,
      callback: (channel: { objects: { laprak: NativeBridge } }) => void,
    ) => void;
    laprakReady?: boolean;
    laprakFlush?: () => void;
    laprakDraftFlush?: (() => Promise<unknown>) | null;
  }
}
let native: NativeBridge;
let sequence = 0;
const pending = new Map<
  number,
  { resolve: (value: unknown) => void; reject: (error: Error) => void }
>();
export function connect(
  onState: (state: State) => void,
  onNotice: (text: string) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!window.qt || !window.QWebChannel) {
      reject(
        new Error(
          "Buka aplikasi melalui Jalankan Laprak.cmd untuk terhubung ke data lokal.",
        ),
      );
      return;
    }
    new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
      native = channel.objects.laprak;
      native.response.connect((raw) => {
        const message = JSON.parse(raw);
        const request = pending.get(message.id);
        if (request) {
          pending.delete(message.id);
          message.error
            ? request.reject(new Error(message.error))
            : request.resolve(message.result);
        }
      });
      native.changed.connect((raw) => onState(JSON.parse(raw)));
      native.notice.connect(onNotice);
      rpc<State>("state")
        .then((state) => {
          onState(state);
          window.laprakReady = true;
          resolve();
        })
        .catch(reject);
    });
  });
}
export function rpc<T = unknown>(
  method: string,
  params: unknown = {},
): Promise<T> {
  return new Promise((resolve, reject) => {
    if (!native) {
      reject(new Error("Koneksi aplikasi belum siap."));
      return;
    }
    const id = ++sequence;
    pending.set(id, { resolve: (value) => resolve(value as T), reject });
    native.request(JSON.stringify({ id, method, params }));
  });
}
