import { useState, useEffect, useRef } from 'preact/hooks';
import { api } from './api';
import { Markdown } from './components/Markdown';

// Strip ANSI escape codes
function cleanStderr(text) {
  if (!text) return text;
  return text
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
    .replace(/\u241b\[[0-9;]*[a-zA-Z]?/g, '');
}

// Parse CSV text into rows
function parseCSV(text) {
  const lines = text.trim().split('\n');
  return lines.map((line) => {
    const row = [];
    let inQuote = false, cell = '';
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { inQuote = !inQuote; }
      else if (ch === ',' && !inQuote) { row.push(cell); cell = ''; }
      else { cell += ch; }
    }
    row.push(cell);
    return row;
  });
}

function fileName(path) {
  const i = path.lastIndexOf('/');
  return i >= 0 ? path.slice(i + 1) : path;
}

function FileContentView({ file }) {
  if (!file) return null;
  const name = fileName(file.path);
  const ct = file.content_type || '';

  // Markdown
  if (ct === 'text/markdown' || name.endsWith('.md')) {
    return <div class="file-view-md"><Markdown content={file.content} /></div>;
  }

  // CSV — render as table
  if (ct === 'text/csv' || name.endsWith('.csv')) {
    const rows = parseCSV(file.content);
    if (rows.length === 0) return <pre class="file-view-pre">{file.content}</pre>;
    const header = rows[0];
    const body = rows.slice(1);
    return (
      <div class="file-view-table-wrap">
        <table class="file-view-table">
          <thead><tr>{header.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
          <tbody>{body.map((row, ri) => (
            <tr key={ri}>{row.map((c, ci) => <td key={ci}>{c}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    );
  }

  // JSON — pretty print
  if (ct === 'application/json' || name.endsWith('.json')) {
    let pretty = file.content;
    try { pretty = JSON.stringify(JSON.parse(file.content), null, 2); } catch {}
    return <pre class="file-view-pre file-view-code">{pretty}</pre>;
  }

  // Images — use raw endpoint
  if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.gif') || name.endsWith('.svg')) {
    const url = api.fileRawURL(file.sessionID, file.path);
    return <div class="file-view-image"><img src={url} alt={name} /></div>;
  }

  // Default: code/text with monospace
  return <pre class="file-view-pre file-view-code">{file.content}</pre>;
}

function FileTree({ node, prefix = '', onOpen }) {
  return (
    <>
      {Object.entries(node.children).sort().map(([name, child]) => (
        <details key={prefix + name} class="ft-dir">
          <summary class="ft-dir-name">{name}/</summary>
          <div class="ft-indent">
            <FileTree node={child} prefix={prefix + name + '/'} onOpen={onOpen} />
          </div>
        </details>
      ))}
      {node.files.sort((a, b) => a.name.localeCompare(b.name)).map((f) => (
        <div key={f.path} class="ft-file" onClick={() => onOpen('/workspace/output/' + f.path)}>
          {f.name}
        </div>
      ))}
    </>
  );
}

export function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [models, setModels] = useState(null);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedTool, setSelectedTool] = useState('opencode');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [scrollTick, setScrollTick] = useState(0);
  const [files, setFiles] = useState([]);
  const [filesOpen, setFilesOpen] = useState(false);
  // Tabs: array of { id, path, content, content_type }
  const [openTabs, setOpenTabs] = useState([]);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or a tab id
  const [loadingFile, setLoadingFile] = useState(false);
  const chatRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    api.getModels().then((m) => {
      setModels(m);
      setSelectedModel(m.default_model || '');
    });
    refreshSessions();
  }, []);

  useEffect(() => {
    if (!activeSession) return;
    api.getMessages(activeSession).then(setMessages).catch(() => setMessages([]));
    api.getSessionJobs(activeSession).then((jobs) => {
      const running = jobs.find((j) => j.status === 'running');
      if (running) {
        setStreaming(true);
        let stdout = '';
        let stderr = '';
        setMessages((m) => [...m, { role: 'assistant', content: '', thinking: '' }]);
        api.streamJob(activeSession, running.id,
          (line, stream) => {
            if (stream === 'stderr') { stderr += line + '\n'; }
            else { stdout += line + '\n'; }
            setMessages((m) => {
              const updated = [...m];
              updated[updated.length - 1] = { role: 'assistant', content: stdout, thinking: stderr };
              return updated;
            });
            setScrollTick((t) => t + 1);
          },
          () => { setStreaming(false); refreshSessions(); }
        );
      }
    }).catch(() => {});
  }, [activeSession]);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, scrollTick]);

  useEffect(() => {
    if (!streaming) return;
    const interval = setInterval(refreshSessions, 3000);
    return () => clearInterval(interval);
  }, [streaming]);

  const refreshFiles = () => {
    if (!activeSession) return;
    api.getFiles(activeSession).then(setFiles).catch(() => setFiles([]));
  };
  useEffect(() => {
    if (activeSession) refreshFiles();
    else { setFiles([]); setOpenTabs([]); setActiveTab('chat'); }
  }, [activeSession]);
  useEffect(() => {
    if (!streaming && activeSession) refreshFiles();
  }, [streaming]);

  const refreshSessions = () => api.listSessions().then(setSessions).catch(() => setSessions([]));

  const createSession = async () => {
    const sess = await api.createSession(selectedTool, '', selectedModel);
    await refreshSessions();
    setActiveSession(sess.ID);
    setMessages([]);
  };

  const stopSession = async (id) => {
    await api.stopSession(id);
    refreshSessions();
  };

  const removeSession = async (id) => {
    await api.removeSession(id);
    if (activeSession === id) {
      setActiveSession(null);
      setMessages([]);
    }
    refreshSessions();
  };

  const sendMessage = async () => {
    if (!input.trim() || streaming) return;
    const prompt = input.trim();
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    // Switch to chat tab when sending
    setActiveTab('chat');

    let sessID = activeSession;
    if (!sessID) {
      const sess = await api.createSession(selectedTool, '', selectedModel);
      await refreshSessions();
      sessID = sess.ID;
      setActiveSession(sessID);
    }

    setMessages((m) => [...m, { role: 'user', content: prompt }]);
    setStreaming(true);
    let stdout = '';
    let stderr = '';

    try {
      const { job_id } = await api.sendMessage(sessID, prompt, selectedModel);
      setMessages((m) => [...m, { role: 'assistant', content: '', thinking: '' }]);

      await new Promise((resolve) => {
        api.streamJob(sessID, job_id,
          (line, stream) => {
            if (stream === 'stderr') { stderr += line + '\n'; }
            else { stdout += line + '\n'; }
            setMessages((m) => {
              const updated = [...m];
              updated[updated.length - 1] = { role: 'assistant', content: stdout, thinking: stderr };
              return updated;
            });
            setScrollTick((t) => t + 1);
          },
          () => { setStreaming(false); refreshSessions(); resolve(); }
        );
      });
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: `**Error:** ${err.message}` }]);
      setStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const autoResize = (e) => {
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const doSearch = async () => {
    if (!searchQuery.trim() || searching) return;
    setSearching(true);
    try {
      const res = await api.search(searchQuery, activeSession || '', 10);
      setSearchResults(res.results || []);
    } catch (err) {
      setSearchResults([{ content: `Search error: ${err.message}`, role: 'error', score: 0 }]);
    }
    setSearching(false);
  };

  // Open a file as a tab in the main area
  const openFile = async (path) => {
    // Check if already open
    const existing = openTabs.find((t) => t.path === path);
    if (existing) {
      setActiveTab(existing.id);
      return;
    }
    setLoadingFile(true);
    try {
      const res = await api.getFileContent(activeSession, path);
      const tab = { id: 'file-' + Date.now(), path: res.path, content: res.content, content_type: res.content_type, sessionID: activeSession };
      setOpenTabs((tabs) => [...tabs, tab]);
      setActiveTab(tab.id);
    } catch (err) {
      const tab = { id: 'file-' + Date.now(), path, content: `Error: ${err.message}`, content_type: 'text/plain', sessionID: activeSession };
      setOpenTabs((tabs) => [...tabs, tab]);
      setActiveTab(tab.id);
    }
    setLoadingFile(false);
  };

  const closeTab = (tabId) => {
    setOpenTabs((tabs) => tabs.filter((t) => t.id !== tabId));
    if (activeTab === tabId) setActiveTab('chat');
  };

  // Build tree from flat file list
  const buildTree = (entries) => {
    const root = { children: {}, files: [] };
    for (const entry of entries) {
      const parts = entry.path.split('/');
      let node = root;
      if (entry.is_dir) {
        for (const p of parts) {
          if (!node.children[p]) node.children[p] = { children: {}, files: [] };
          node = node.children[p];
        }
      } else {
        const dir = parts.slice(0, -1);
        for (const p of dir) {
          if (!node.children[p]) node.children[p] = { children: {}, files: [] };
          node = node.children[p];
        }
        node.files.push(entry);
      }
    }
    return root;
  };

  const modelOptions = [];
  if (models?.providers) {
    for (const [provider, data] of Object.entries(models.providers)) {
      for (const model of Object.keys(data.models || {})) {
        modelOptions.push(`${provider}/${model}`);
      }
    }
  }

  const activeInfo = sessions.find((s) => s.ID === activeSession);
  const activeFileTab = openTabs.find((t) => t.id === activeTab);
  const showChat = activeTab === 'chat';

  return (
    <>
      {/* ── Sidebar ── */}
      <div class="sidebar">
        <div class="sidebar-top">
          <button class="new-chat-btn" onClick={createSession}>
            <span>+</span> New Chat
          </button>
          <input
            class="search-input"
            type="text"
            value={searchQuery}
            onInput={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder="Search conversations..."
          />
        </div>

        {searchResults && (
          <div class="search-results-panel">
            <div class="search-results-header">
              <span>{searchResults.length} results</span>
              <button onClick={() => setSearchResults(null)}>Clear</button>
            </div>
            {searchResults.map((r, i) => (
              <div key={i} class="sr-item">
                <div class="sr-meta">
                  <span>{r.role}</span>
                  <span class="sr-score">{(r.score * 100).toFixed(0)}%</span>
                </div>
                <div class="sr-content">{r.content?.slice(0, 200)}</div>
              </div>
            ))}
          </div>
        )}

        <div class="session-list">
          {sessions.map((s) => (
            <div
              key={s.ID}
              class={`session-item ${s.ID === activeSession ? 'active' : ''}`}
              onClick={() => setActiveSession(s.ID)}
            >
              <span class={`session-dot dot-${s.Status}`} />
              <div class="session-meta">
                <div class="session-name">{s.Tool} · {s.ID.slice(0, 8)}</div>
                <div class="session-sub">{s.Status}</div>
              </div>
            </div>
          ))}
          {sessions.length === 0 && (
            <div style={{ padding: '16px 12px', color: 'var(--text-muted)', fontSize: '13px' }}>
              No sessions yet
            </div>
          )}
        </div>

        <div class="sidebar-bottom">
          <div class="sidebar-bottom-row">
            <select class="sidebar-select" value={selectedTool} onChange={(e) => setSelectedTool(e.target.value)}>
              <option value="opencode">OpenCode</option>
              <option value="claude">Claude</option>
              <option value="codex">Codex</option>
              <option value="bash">Bash</option>
            </select>
            <select class="sidebar-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
              {modelOptions.map((m) => (
                <option key={m} value={m}>{m.split('/').pop()}</option>
              ))}
            </select>
          </div>
          <button class="new-session-btn" onClick={createSession}>New Session</button>
        </div>
      </div>

      {/* ── Main ── */}
      <div class="main">
        {activeSession && (
          <div class="chat-header">
            <div class="chat-header-title">
              {activeInfo?.Tool || 'Session'}
              <span class="chat-header-sub">{activeSession.slice(0, 12)}</span>
              {streaming && (
                <span class="chat-header-sub" style={{ color: 'var(--green)' }}> streaming...</span>
              )}
            </div>
            <button class={`header-btn ${filesOpen ? 'active' : ''}`} onClick={() => { setFilesOpen(!filesOpen); if (!filesOpen) refreshFiles(); }}>Files</button>
            <button class="header-btn" onClick={() => stopSession(activeSession)}>Stop</button>
            <button class="header-btn danger" onClick={() => removeSession(activeSession)}>Remove</button>
          </div>
        )}

        {/* Tab bar — only show when we have file tabs open */}
        {activeSession && openTabs.length > 0 && (
          <div class="tab-bar">
            <div
              class={`tab-item ${showChat ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              Chat
            </div>
            {openTabs.map((tab) => (
              <div
                key={tab.id}
                class={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span class="tab-name">{fileName(tab.path)}</span>
                <span class="tab-close" onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}>x</span>
              </div>
            ))}
          </div>
        )}

        {/* Chat view */}
        {showChat && activeSession && messages.length > 0 ? (
          <div class="chat" ref={chatRef}>
            {messages.filter(m => m.content_type !== 'stderr').map((msg, i, arr) => {
              const isUser = msg.role === 'user';
              const isLast = i === arr.length - 1;
              let thinking = '';
              if (msg.role === 'assistant' && msg.content_type !== 'stderr') {
                const idx = messages.indexOf(msg);
                const prev = messages[idx - 1];
                const next = messages[idx + 1];
                if (prev && prev.content_type === 'stderr') {
                  thinking = cleanStderr(prev.content);
                } else if (next && next.content_type === 'stderr') {
                  thinking = cleanStderr(next.content);
                }
              }
              if (msg.thinking) thinking = cleanStderr(msg.thinking);

              return isUser ? (
                <div key={i} class="msg-user">
                  <div class="msg-user-bubble">{msg.content}</div>
                </div>
              ) : (
                <div key={i} class="msg-assistant">
                  <div class="msg-avatar">AI</div>
                  <div class={`msg-assistant-bubble ${streaming && isLast ? 'streaming-cursor' : ''}`}>
                    {thinking && (
                      <details class="thinking-block">
                        <summary class="thinking-summary">
                          Thinking{streaming && isLast ? '...' : ''}
                        </summary>
                        <pre class="thinking-content">{thinking}</pre>
                      </details>
                    )}
                    <Markdown content={msg.content} />
                  </div>
                </div>
              );
            })}
          </div>
        ) : showChat && !activeSession ? (
          <div class="landing">
            <div class="landing-logo">CLI Sandbox</div>
            <div class="landing-sub">Sandboxed AI coding sessions</div>
            <div class="landing-input">
              <div class="input-bar">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onInput={(e) => { setInput(e.target.value); autoResize(e); }}
                  onKeyDown={handleKeyDown}
                  placeholder="What do you want to know?"
                  rows={1}
                  disabled={streaming}
                />
                <button class="send-btn" onClick={sendMessage} disabled={streaming || !input.trim()}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div class="landing-chips">
              <button class="chip" onClick={() => { setInput('Analyze mining stocks in India'); }}>Mining Stocks</button>
              <button class="chip" onClick={() => { setInput('Backtest RSI strategy on NIFTY 50'); }}>RSI Backtest</button>
              <button class="chip" onClick={() => { setInput('How does monsoon affect agriculture stocks?'); }}>Monsoon Impact</button>
            </div>
          </div>
        ) : showChat && activeSession && messages.length === 0 ? (
          <div class="landing">
            <div class="landing-logo">CLI Sandbox</div>
            <div class="landing-sub">Sandboxed AI coding sessions</div>
            <div class="landing-input">
              <div class="input-bar">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onInput={(e) => { setInput(e.target.value); autoResize(e); }}
                  onKeyDown={handleKeyDown}
                  placeholder="What do you want to know?"
                  rows={1}
                  disabled={streaming}
                />
                <button class="send-btn" onClick={sendMessage} disabled={streaming || !input.trim()}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {/* File tab view — full width in main area */}
        {activeFileTab && (
          <div class="file-tab-view">
            <div class="file-tab-path">{activeFileTab.path}</div>
            <div class="file-tab-content">
              <FileContentView file={activeFileTab} />
            </div>
          </div>
        )}

        {showChat && activeSession && messages.length > 0 && (
          <div class="input-area">
            <div class="input-bar">
              <textarea
                ref={textareaRef}
                value={input}
                onInput={(e) => { setInput(e.target.value); autoResize(e); }}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything..."
                rows={1}
                disabled={streaming}
              />
              <button class="send-btn" onClick={sendMessage} disabled={streaming || !input.trim()}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Right sidebar: File tree ── */}
      {filesOpen && activeSession && (
        <div class="files-panel">
          <div class="files-header">
            <span>Output Files</span>
            <button onClick={() => refreshFiles()}>Refresh</button>
            <button onClick={() => setFilesOpen(false)}>Close</button>
          </div>
          <div class="file-tree">
            {files.length === 0 ? (
              <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No output files yet
              </div>
            ) : (
              <FileTree node={buildTree(files)} onOpen={openFile} />
            )}
          </div>
        </div>
      )}
    </>
  );
}
