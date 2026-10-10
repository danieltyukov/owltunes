// DOM lookup shared by the pages.

export function $<T extends HTMLElement = HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (el === null) {
    throw new Error(`missing #${id}`);
  }
  return el as T;
}
