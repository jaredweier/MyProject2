/* Chronos offline multi-page API cache + mutation queue + flush (v3 residual close) */
(function () {
  var SNAP_KEY = "chronos_offline_snapshot_v1";
  var MULTI_KEY = "chronos_offline_pages_v2";
  var QUEUE_KEY = "chronos_offline_mutation_queue_v1";

  function saveSnapshot(text, extra) {
    try {
      var payload = {
        saved_at: new Date().toISOString(),
        text: String(text || "").slice(0, 16000),
        extra: extra || {},
      };
      localStorage.setItem(SNAP_KEY, JSON.stringify(payload));
    } catch (e) {}
  }

  function saveMultiPage(apiJson) {
    try {
      localStorage.setItem(
        MULTI_KEY,
        JSON.stringify({
          saved_at: new Date().toISOString(),
          data: apiJson,
        })
      );
      if (apiJson && apiJson.text) {
        saveSnapshot(apiJson.text, { source: "api/offline/snapshot" });
      }
    } catch (e) {}
  }

  function getMultiPage() {
    try {
      return JSON.parse(localStorage.getItem(MULTI_KEY) || "null");
    } catch (e) {
      return null;
    }
  }

  function enqueueMutation(action, payload) {
    try {
      var q = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
      if (!Array.isArray(q)) q = [];
      q.push({
        id: Date.now() + "-" + Math.random().toString(36).slice(2, 8),
        action: String(action || "unknown"),
        payload: payload || {},
        queued_at: new Date().toISOString(),
      });
      localStorage.setItem(QUEUE_KEY, JSON.stringify(q.slice(-50)));
      return true;
    } catch (e) {
      return false;
    }
  }

  function getMutationQueue() {
    try {
      return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]") || [];
    } catch (e) {
      return [];
    }
  }

  function clearMutationQueue() {
    try {
      localStorage.removeItem(QUEUE_KEY);
    } catch (e) {}
  }

  function setMutationQueue(q) {
    try {
      localStorage.setItem(QUEUE_KEY, JSON.stringify(q || []));
    } catch (e) {}
  }

  function onlineBanner() {
    var old = document.getElementById("chronos-offline-banner");
    if (old) old.remove();
    if (navigator.onLine) return;
    var b = document.createElement("div");
    b.id = "chronos-offline-banner";
    b.className = "offline-banner";
    var q = getMutationQueue();
    b.textContent =
      "Offline — multi-page shell + last API snapshot. Mutations queue for flush when online" +
      (q.length ? " · " + q.length + " draft(s) queued" : "") +
      ". Open /static/offline.html";
    document.body.prepend(b);
  }

  function fetchAndCacheSnapshot() {
    if (!navigator.onLine) return;
    try {
      fetch("/api/offline/snapshot", { credentials: "same-origin" })
        .then(function (r) {
          if (!r || !r.ok) return null;
          return r.json();
        })
        .then(function (data) {
          if (data && data.success) saveMultiPage(data);
        })
        .catch(function () {});
    } catch (e) {}
  }

  /** Flush queued mutations to server when back online */
  function flushMutationQueue() {
    if (!navigator.onLine) return Promise.resolve({ skipped: true });
    var q = getMutationQueue();
    if (!q.length) return Promise.resolve({ empty: true });
    return fetch("/api/offline/mutations", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: q }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { http: r.status, data: data };
        });
      })
      .then(function (res) {
        var data = res.data || {};
        var results = data.results || [];
        // Drop successful / skipped-unknown items; keep hard failures for retry
        var keep = [];
        var byId = {};
        results.forEach(function (r) {
          if (r && r.id) byId[r.id] = r;
        });
        q.forEach(function (item) {
          var r = byId[item.id];
          if (!r) {
            keep.push(item);
            return;
          }
          if (r.success || r.skipped) return;
          // failed — retry later
          item.last_error = r.message || "failed";
          keep.push(item);
        });
        setMutationQueue(keep);
        try {
          if (data.applied) {
            console.info("[chronos] offline mutations applied", data.applied, "failed", data.failed);
          }
        } catch (e) {}
        return data;
      })
      .catch(function (err) {
        return { success: false, message: String(err) };
      });
  }

  window.addEventListener("online", function () {
    onlineBanner();
    fetchAndCacheSnapshot();
    flushMutationQueue();
  });
  window.addEventListener("offline", onlineBanner);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      onlineBanner();
      fetchAndCacheSnapshot();
      if (navigator.onLine) flushMutationQueue();
    });
  } else {
    onlineBanner();
    fetchAndCacheSnapshot();
    if (navigator.onLine) flushMutationQueue();
  }

  window.chronosOffline = {
    saveSnapshot: saveSnapshot,
    getSnapshot: function () {
      try {
        return JSON.parse(localStorage.getItem(SNAP_KEY) || "null");
      } catch (e) {
        return null;
      }
    },
    saveMultiPage: saveMultiPage,
    getMultiPage: getMultiPage,
    enqueueMutation: enqueueMutation,
    getMutationQueue: getMutationQueue,
    clearMutationQueue: clearMutationQueue,
    flushMutationQueue: flushMutationQueue,
    refreshSnapshot: fetchAndCacheSnapshot,
  };

  try {
    saveSnapshot(
      "Last online page: " + (document.title || "") + "\n" + location.href,
      { path: location.pathname }
    );
  } catch (e) {}
})();
