export const TOAST_EVENT = 'kpi-toast';

export interface ToastMessage {
  id: number;
  text: string;
}

let nextId = 1;

/** Shows an error toast (rendered by <Toasts />; also used by the global mutation error handler). */
export function notifyError(text: string) {
  window.dispatchEvent(new CustomEvent<ToastMessage>(TOAST_EVENT, { detail: { id: nextId++, text } }));
}
