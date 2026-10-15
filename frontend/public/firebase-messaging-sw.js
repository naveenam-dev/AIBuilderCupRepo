// Firebase Cloud Messaging service worker: shows on-call pages as system notifications when the tab is
// in the background. The public Firebase web config arrives in this script's URL (?config=...).
importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js");

const config = JSON.parse(new URL(self.location.href).searchParams.get("config") || "{}");
if (config.apiKey) {
  firebase.initializeApp(config);
  firebase.messaging(); // notification payloads are displayed automatically
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) =>
      wins.length ? wins[0].focus() : self.clients.openWindow("/"),
    ),
  );
});
