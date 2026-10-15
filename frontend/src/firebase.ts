// Firebase client: Auth (persona custom tokens + Google sign-in), live Firestore reads, Cloud Messaging push.
import { initializeApp, type FirebaseApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithCustomToken, signInWithPopup, type Auth } from "firebase/auth";
import { collection, getFirestore, limit, onSnapshot, orderBy, query, where, type Firestore } from "firebase/firestore";
import { getMessaging, getToken, isSupported } from "firebase/messaging";
import type { Action, InboxMessage } from "./types";

let app: FirebaseApp | undefined;
let auth: Auth;
let db: Firestore;
let options: FirebaseOptions;

export function initFirebase(config: FirebaseOptions) {
  if (app) return;
  options = config;
  app = initializeApp(config);
  auth = getAuth(app);
  db = getFirestore(app);
}

export const firebaseEnabled = () => app !== undefined;

export async function signInPersona(customToken: string) {
  await signInWithCustomToken(auth, customToken);
}

export async function signInGoogle() {
  await signInWithPopup(auth, new GoogleAuthProvider());
}

export async function idToken(): Promise<string> {
  if (!auth.currentUser) throw new Error("Not signed in");
  return auth.currentUser.getIdToken();
}

/** Live status of the signed-in user's approval cards (Firestore rules limit this to their own actions). */
export function watchActions(uid: string, onChange: (a: Partial<Action> & { id: string }) => void, onError: (e: Error) => void) {
  return onSnapshot(
    query(collection(db, "actions"), where("requested_by", "==", uid)),
    (snap) => {
      snap.docChanges().forEach((ch) => {
        const d = ch.doc.data();
        onChange({ id: ch.doc.id, status: d.status, result: d.result ?? null, summary: d.summary, tool: d.tool, args: d.args });
      });
    },
    onError,
  );
}

/** Pages addressed to the signed-in user, newest first. `fresh` holds messages that arrived after the first load. */
export function watchInbox(uid: string, onChange: (all: InboxMessage[], fresh: InboxMessage[]) => void, onError: (e: Error) => void) {
  let first = true;
  const q = query(collection(db, "users", uid, "inbox"), orderBy("created_at", "desc"), limit(8));
  return onSnapshot(
    q,
    (snap) => {
      const all = snap.docs.map((d) => toMessage(d.id, d.data()));
      const fresh = first ? [] : snap.docChanges().filter((c) => c.type === "added").map((c) => toMessage(c.doc.id, c.doc.data()));
      first = false;
      onChange(all, fresh);
    },
    onError,
  );
}

function toMessage(id: string, d: Record<string, any>): InboxMessage {
  const at = d.created_at?.toDate ? d.created_at.toDate() : new Date(d.created_at);
  return { id, target: d.target, text: d.text, sender: d.sender, created_at: at.toISOString() };
}

/** Ask for notification permission and return this browser's FCM token (null if unsupported or denied). */
export async function enablePush(): Promise<string | null> {
  if (!(await isSupported()) || !("serviceWorker" in navigator)) return null;
  if ((await Notification.requestPermission()) !== "granted") return null;
  // The service worker reads the public web config from its URL, so it can initialize synchronously.
  const sw = await navigator.serviceWorker.register(`/firebase-messaging-sw.js?config=${encodeURIComponent(JSON.stringify(options))}`);
  return getToken(getMessaging(app), { serviceWorkerRegistration: sw });
}
