const BASE = '/api';

async function json(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  getModels: () => fetch(`${BASE}/config/models`).then(json),

  createSession: (tool, workspace, model, byoKeys) =>
    fetch(`${BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, workspace, model, byo_keys: byoKeys }),
    }).then(json),

  listSessions: () => fetch(`${BASE}/sessions`).then(json),

  exec: (sessionID, cmd) =>
    fetch(`${BASE}/sessions/${sessionID}/exec`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd }),
    }).then(json),

  stopSession: (sessionID) =>
    fetch(`${BASE}/sessions/${sessionID}/stop`, { method: 'POST' }).then(json),

  removeSession: (sessionID) =>
    fetch(`${BASE}/sessions/${sessionID}`, { method: 'DELETE' }).then(json),

  getMessages: (sessionID) =>
    fetch(`${BASE}/sessions/${sessionID}/messages`).then(json),

  sendMessage: (sessionID, content, model) =>
    fetch(`${BASE}/sessions/${sessionID}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, model }),
    }).then(json),

  createJob: (sessionID, cmd, description) =>
    fetch(`${BASE}/sessions/${sessionID}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd, description }),
    }).then(json),

  getJob: (sessionID, jobID) =>
    fetch(`${BASE}/sessions/${sessionID}/jobs/${jobID}`).then(json),

  getSessionJobs: (sessionID) =>
    fetch(`${BASE}/sessions/${sessionID}/jobs`).then(json),

  search: (query, sessionID, k = 10) =>
    fetch(`${BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, session_id: sessionID || '', k }),
    }).then(json),

  getFiles: (sessionID, path = '/workspace/output') =>
    fetch(`${BASE}/sessions/${sessionID}/files?path=${encodeURIComponent(path)}`).then(json),

  getFileContent: (sessionID, path) =>
    fetch(`${BASE}/sessions/${sessionID}/files/content?path=${encodeURIComponent(path)}`).then(json),

  fileRawURL: (sessionID, path) =>
    `${BASE}/sessions/${sessionID}/files/raw?path=${encodeURIComponent(path)}`,

  streamJob: (sessionID, jobID, onData, onDone) => {
    const es = new EventSource(`${BASE}/sessions/${sessionID}/jobs/${jobID}/stream`);
    es.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.event === 'done') {
        es.close();
        onDone?.(msg.status);
      } else if (msg.event === 'output') {
        onData?.(msg.data, msg.stream || 'stdout');
      }
    };
    es.onerror = () => {
      es.close();
      onDone?.('error');
    };
    return () => es.close();
  },
};
