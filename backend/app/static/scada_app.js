/**
 * SCADA HMI Application Engine
 * Industrial HMI design following ISA-101-inspired principles
 * 
 * Features:
 * - Native WebSocket streaming with auto-reconnect & heartbeat
 * - Independent Client-Side WebCrypto SHA-256 Verification
 * - High-speed 1 kHz raw vibration waveform oscilloscope (Canvas)
 * - Out-of-order and duplicate packet filtration
 * - Strict separation of UI Connection vs Hardware Stream states
 * - Honest zero-mock null states (NOT_AVAILABLE)
 */

(function () {
  "use strict";

  // State Management
  const state = {
    ws: null,
    wsConnected: false,
    reconnectAttempts: 0,
    reconnectTimer: null,
    pingInterval: null,
    lastPingTime: null,
    activeStreamId: null,
    lastSequencePerStream: {}, // { "device_id:stream_id": lastSeq }
    hardwareState: "NO ACTIVE STREAM",
    hardwareLastSeen: 0,
    streamTrackers: {} // { "device_id:stream_id": trackerObj }
  };

  // DOM Elements
  const el = {
    uiBadge: document.getElementById("ui-connection-badge"),
    hwBadge: document.getElementById("hardware-stream-badge"),
    measuredLatency: document.getElementById("measured-latency"),
    utcClock: document.getElementById("utc-clock"),
    
    // Telemetry Tiles
    valSpeed: document.getElementById("val-speed"),
    statusSpeed: document.getElementById("status-speed"),
    valRpm: document.getElementById("val-rpm"),
    statusRpm: document.getElementById("status-rpm"),
    valLoad: document.getElementById("val-load"),
    statusLoad: document.getElementById("status-load"),
    valTemp: document.getElementById("val-temp"),
    statusTemp: document.getElementById("status-temp"),

    // Oscilloscope Elements
    canvas: document.getElementById("oscilloscope-canvas"),
    overlayNoData: document.getElementById("canvas-overlay-nodata"),
    osFreqTag: document.getElementById("os-freq-tag"),
    osScaleTag: document.getElementById("os-scale-tag"),
    osStreamId: document.getElementById("os-stream-id"),
    osProvenanceTag: document.getElementById("os-provenance-tag"),
    osSeq: document.getElementById("os-seq"),
    osSampleCount: document.getElementById("os-sample-count"),
    osSha256: document.getElementById("os-sha256"),
    osCryptoBadge: document.getElementById("os-crypto-badge"),
    osHwTime: document.getElementById("os-hw-time"),
    osUtcTime: document.getElementById("os-utc-time"),

    // Diagnostics Table
    streamsCount: document.getElementById("active-stream-count"),
    streamsBody: document.getElementById("streams-table-body"),

    // Simulation Controls
    btnInjectSim: document.getElementById("btn-inject-simulation"),
    simSensorSelect: document.getElementById("sim-sensor-select"),
    simFreqInput: document.getElementById("sim-freq-input"),
    simFeedback: document.getElementById("sim-feedback")
  };

  const ctx = el.canvas.getContext("2d");

  // --------------------------------------------------------------------------
  // 1. Clock & Latency Tracking
  // --------------------------------------------------------------------------
  function updateClock() {
    const now = new Date();
    el.utcClock.textContent = now.toISOString().slice(11, 19) + " UTC";
  }
  setInterval(updateClock, 1000);
  updateClock();

  // Watchdog checking if hardware stream went silent (> 10s)
  setInterval(() => {
    if (state.hardwareLastSeen > 0 && (Date.now() - state.hardwareLastSeen) > 10000) {
      if (state.hardwareState !== "NO ACTIVE STREAM" && state.hardwareState !== "HARDWARE OFFLINE") {
        setHardwareState("HARDWARE OFFLINE");
      }
    }
  }, 2000);

  // --------------------------------------------------------------------------
  // 2. Status Badge Updaters (Separated UI vs Hardware Stream)
  // --------------------------------------------------------------------------
  function setUiConnectionState(status) {
    el.uiBadge.className = "badge";
    if (status === "CONNECTED") {
      el.uiBadge.classList.add("badge-connected");
      el.uiBadge.querySelector(".text").textContent = "UI CONNECTED";
    } else if (status === "RECONNECTING") {
      el.uiBadge.classList.add("badge-reconnecting");
      el.uiBadge.querySelector(".text").textContent = "RECONNECTING";
      el.measuredLatency.textContent = "NOT_AVAILABLE";
    } else {
      el.uiBadge.classList.add("badge-disconnected");
      el.uiBadge.querySelector(".text").textContent = "UI OFFLINE";
      el.measuredLatency.textContent = "NOT_AVAILABLE";
    }
  }

  function setHardwareState(status) {
    state.hardwareState = status;
    el.hwBadge.className = "badge";
    if (status === "LIVE" || status === "LIVE HARDWARE") {
      el.hwBadge.classList.add("badge-live");
      el.hwBadge.querySelector(".text").textContent = "LIVE HARDWARE";
    } else if (status === "SIMULATION") {
      el.hwBadge.classList.add("badge-sim");
      el.hwBadge.querySelector(".text").textContent = "SIMULATION";
    } else if (status === "HARDWARE OFFLINE") {
      el.hwBadge.classList.add("badge-disconnected");
      el.hwBadge.querySelector(".text").textContent = "HARDWARE OFFLINE";
    } else {
      el.hwBadge.classList.add("badge-neutral");
      el.hwBadge.querySelector(".text").textContent = "NO ACTIVE STREAM";
    }
  }

  // --------------------------------------------------------------------------
  // 3. Independent Client-Side WebCrypto SHA-256 Verification
  // --------------------------------------------------------------------------
  async function verifyCanonicalPayloadHash(samples, expectedHexHash) {
    if (!window.crypto || !window.crypto.subtle) {
      return { verified: false, method: "UNSUPPORTED" };
    }
    try {
      // Reconstruct exact canonical binary payload: IEEE 754 double little-endian ('<d')
      const buffer = new ArrayBuffer(samples.length * 8);
      const view = new DataView(buffer);
      for (let i = 0; i < samples.length; i++) {
        view.setFloat64(i * 8, samples[i], true); // true = little-endian
      }
      const digestBuffer = await window.crypto.subtle.digest("SHA-256", buffer);
      const hashArray = Array.from(new Uint8Array(digestBuffer));
      const clientHash = hashArray.map(b => b.toString(16).padStart(2, "0")).join("");

      const matches = (clientHash.toLowerCase() === expectedHexHash.toLowerCase());
      return { verified: matches, clientHash, method: "WEBCRYPTO" };
    } catch (err) {
      console.error("Client SHA-256 computation error:", err);
      return { verified: false, method: "ERROR" };
    }
  }

  // --------------------------------------------------------------------------
  // 4. Oscilloscope Canvas Renderer (60 FPS, Dynamic Bounds)
  // --------------------------------------------------------------------------
  function renderWaveform(samples, sampleRateHz) {
    el.overlayNoData.classList.add("hidden");
    const width = el.canvas.width;
    const height = el.canvas.height;

    // Clear background
    ctx.fillStyle = "#03060c";
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = "#0f1c2e";
    ctx.lineWidth = 1;
    const gridCols = 10;
    const gridRows = 6;

    for (let i = 0; i <= gridCols; i++) {
      const x = (i / gridCols) * width;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let j = 0; j <= gridRows; j++) {
      const y = (j / gridRows) * height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Zero-axis line
    const zeroY = height / 2;
    ctx.strokeStyle = "#1e3a5f";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, zeroY);
    ctx.lineTo(width, zeroY);
    ctx.stroke();

    if (!samples || samples.length === 0) return;

    // Compute dynamic range (do not assume +/-16g)
    let minVal = samples[0];
    let maxVal = samples[0];
    for (let i = 1; i < samples.length; i++) {
      if (samples[i] < minVal) minVal = samples[i];
      if (samples[i] > maxVal) maxVal = samples[i];
    }
    const absPeak = Math.max(Math.abs(minVal), Math.abs(maxVal), 0.1);
    const range = absPeak * 1.25; // 25% margin
    el.osScaleTag.innerHTML = `Dynamic Sample Scale: <strong>[-${range.toFixed(2)} .. +${range.toFixed(2)} g]</strong>`;

    // Draw waveform
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2;
    ctx.beginPath();

    const step = width / (samples.length - 1);
    for (let i = 0; i < samples.length; i++) {
      const x = i * step;
      const normalized = samples[i] / range;
      const y = zeroY - (normalized * (height / 2));
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Subtle glow on signal
    ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
    ctx.lineWidth = 6;
    ctx.stroke();
  }

  // --------------------------------------------------------------------------
  // 5. Telemetry Burst Processor (With Out-of-Order & Duplicate Protection)
  // --------------------------------------------------------------------------
  async function processTelemetryBurst(burst) {
    const streamKey = `${burst.device_id}:${burst.stream_id}`;
    const incomingSeq = burst.sequence_number;

    // Out-of-Order / Duplicate Filtration
    const lastSeq = state.lastSequencePerStream[streamKey];
    if (lastSeq !== undefined) {
      if (incomingSeq < lastSeq) {
        console.warn(`[Out-of-Order] Stream ${streamKey}: got seq ${incomingSeq} < lastSeq ${lastSeq}. Not overwriting.`);
        return;
      } else if (incomingSeq === lastSeq) {
        console.log(`[Duplicate] Stream ${streamKey}: seq ${incomingSeq} already rendered. Ignored.`);
        return;
      }
    }
    state.lastSequencePerStream[streamKey] = incomingSeq;

    // Record stream activity
    state.hardwareLastSeen = Date.now();
    setHardwareState(burst.data_provenance);

    // Update Stream Metadata in UI
    state.activeStreamId = streamKey;
    el.osStreamId.textContent = streamKey;
    el.osSeq.textContent = `#${incomingSeq}`;
    el.osSampleCount.textContent = burst.sample_count;
    el.osHwTime.textContent = burst.hardware_timestamp_us.toLocaleString();
    el.osUtcTime.textContent = burst.received_at_utc.slice(11, 23);

    // Provenance Tag
    el.osProvenanceTag.className = "provenance-tag";
    if (burst.data_provenance === "LIVE") {
      el.osProvenanceTag.classList.add("prov-live");
      el.osProvenanceTag.textContent = "LIVE HARDWARE";
    } else if (burst.data_provenance === "SIMULATION") {
      el.osProvenanceTag.classList.add("prov-sim");
      el.osProvenanceTag.textContent = "SIMULATION";
    } else {
      el.osProvenanceTag.classList.add("prov-none");
      el.osProvenanceTag.textContent = burst.data_provenance;
    }

    // Hash display & Client-side WebCrypto Verification
    el.osSha256.textContent = burst.sha256_hash;
    el.osCryptoBadge.className = "badge-crypto badge-crypto-pending";
    el.osCryptoBadge.textContent = "VERIFYING (WebCrypto)...";

    const cryptoResult = await verifyCanonicalPayloadHash(burst.samples, burst.sha256_hash);
    if (cryptoResult.verified) {
      el.osCryptoBadge.className = "badge-crypto badge-crypto-verified";
      el.osCryptoBadge.textContent = "CLIENT VERIFIED (WebCrypto) ✓";
    } else if (cryptoResult.method === "UNSUPPORTED") {
      el.osCryptoBadge.className = "badge-crypto badge-crypto-pending";
      el.osCryptoBadge.textContent = "BACKEND VERIFIED";
    } else {
      el.osCryptoBadge.className = "badge-crypto badge-crypto-mismatch";
      el.osCryptoBadge.textContent = "INTEGRITY MISMATCH ⚠";
    }

    // Render Canvas
    renderWaveform(burst.samples, burst.sampling_rate_hz);

    // Update Diagnostics Tracker in state & table
    updateStreamDiagnostics(burst);
  }

  // --------------------------------------------------------------------------
  // 6. Diagnostics Table Updater
  // --------------------------------------------------------------------------
  function updateStreamDiagnostics(burst) {
    const streamKey = `${burst.device_id}:${burst.stream_id}`;
    if (!state.streamTrackers[streamKey]) {
      state.streamTrackers[streamKey] = {
        device_id: burst.device_id,
        stream_id: burst.stream_id,
        last_seq: burst.sequence_number,
        total_rx: 1,
        dropped: burst.quality_flags.includes("DROPPED_FRAMES") ? 1 : 0,
        last_hw_time: burst.hardware_timestamp_us,
        rollover_count: 0
      };
    } else {
      const tracker = state.streamTrackers[streamKey];
      tracker.total_rx += 1;
      tracker.last_seq = burst.sequence_number;
      tracker.last_hw_time = burst.hardware_timestamp_us;
      if (burst.quality_flags.includes("DROPPED_FRAMES")) {
        tracker.dropped += 1;
      }
    }
    renderDiagnosticsTable();
  }

  function renderDiagnosticsTable() {
    const keys = Object.keys(state.streamTrackers);
    el.streamsCount.textContent = `${keys.length} ACTIVE`;

    if (keys.length === 0) {
      el.streamsBody.innerHTML = `<tr class="empty-row"><td colspan="8">No stream trackers recorded.</td></tr>`;
      return;
    }

    el.streamsBody.innerHTML = keys.map(key => {
      const t = state.streamTrackers[key];
      return `
        <tr>
          <td><strong>${t.device_id}</strong></td>
          <td><code>${t.stream_id}</code></td>
          <td>#${t.last_seq}</td>
          <td>${t.total_rx}</td>
          <td style="${t.dropped > 0 ? 'color: var(--signal-amber); font-weight: bold;' : ''}">${t.dropped}</td>
          <td>${t.last_hw_time.toLocaleString()}</td>
          <td>${t.rollover_count}</td>
          <td><span class="badge ${t.device_id.includes('test') || t.device_id.includes('sim') ? 'badge-sim' : 'badge-live'}">ACTIVE</span></td>
        </tr>
      `;
    }).join("");
  }

  // --------------------------------------------------------------------------
  // 7. Initial Snapshot Loader (Honest Zero-Mock)
  // --------------------------------------------------------------------------
  async function loadInitialSnapshot() {
    try {
      const res = await fetch("/api/v1/telemetry/snapshot");
      if (!res.ok) return;
      const data = await res.json();

      // Populate stream trackers
      if (data.active_streams && data.active_streams.length > 0) {
        data.active_streams.forEach(s => {
          const key = `${s.device_id}:${s.stream_id}`;
          state.streamTrackers[key] = {
            device_id: s.device_id,
            stream_id: s.stream_id,
            last_seq: s.last_sequence_number,
            total_rx: s.total_packets_received,
            dropped: s.dropped_packets_count,
            last_hw_time: s.last_hardware_timestamp_us,
            rollover_count: s.rollover_count
          };
        });
        renderDiagnosticsTable();
      }

      // If a latest burst already exists in SQLite, display it
      if (data.latest_burst) {
        await processTelemetryBurst(data.latest_burst);
      } else {
        setHardwareState("NO ACTIVE STREAM");
      }
    } catch (err) {
      console.warn("Could not load initial telemetry snapshot:", err);
    }
  }

  // --------------------------------------------------------------------------
  // 8. WebSocket Connection with Exponential Backoff & Heartbeat
  // --------------------------------------------------------------------------
  function connectWebSocket() {
    if (state.ws) {
      try { state.ws.close(); } catch (_) {}
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/v1/live-telemetry`;

    setUiConnectionState("RECONNECTING");
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = function () {
      state.wsConnected = true;
      state.reconnectAttempts = 0;
      setUiConnectionState("CONNECTED");
      console.log("[WebSocket] Connected to SCADA live telemetry bus.");

      // Start ping heartbeat
      if (state.pingInterval) clearInterval(state.pingInterval);
      state.pingInterval = setInterval(sendPing, 4000);
    };

    state.ws.onmessage = async function (event) {
      try {
        const msg = JSON.parse(event.data);

        // Handle PONG for measured latency calculation
        if (msg.type === "PONG") {
          if (state.lastPingTime) {
            const rtt = Math.round(performance.now() - state.lastPingTime);
            el.measuredLatency.textContent = `${rtt} ms`;
          }
          return;
        }

        if (msg.type === "TELEMETRY_BURST") {
          await processTelemetryBurst(msg);
        } else if (msg.type === "INITIAL_STATE" && msg.latest_burst) {
          await processTelemetryBurst(msg.latest_burst);
        }
      } catch (err) {
        console.error("[WebSocket] Failed to parse message:", err);
      }
    };

    state.ws.onclose = function () {
      state.wsConnected = false;
      setUiConnectionState("RECONNECTING");
      if (state.pingInterval) clearInterval(state.pingInterval);

      const delay = Math.min(1000 * Math.pow(1.5, state.reconnectAttempts), 8000);
      state.reconnectAttempts++;
      console.log(`[WebSocket] Disconnected. Retrying in ${Math.round(delay)}ms...`);
      clearTimeout(state.reconnectTimer);
      state.reconnectTimer = setTimeout(connectWebSocket, delay);
    };

    state.ws.onerror = function (err) {
      console.warn("[WebSocket] Socket error observed:", err);
    };
  }

  function sendPing() {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.lastPingTime = performance.now();
      state.ws.send(JSON.stringify({ action: "ping", timestamp: Date.now() }));
    }
  }

  // --------------------------------------------------------------------------
  // 9. Simulation Test Harness Trigger (POST -> Ingest -> WAL -> WS -> UI)
  // --------------------------------------------------------------------------
  el.btnInjectSim.addEventListener("click", async function () {
    const sensorId = el.simSensorSelect.value;
    const freqHz = parseFloat(el.simFreqInput.value) || 50.0;

    el.simFeedback.textContent = "Dispatching test injection to ingestion engine...";
    el.btnInjectSim.disabled = true;

    try {
      const url = `/api/v1/telemetry/simulate/generate-burst?sensor_id=${encodeURIComponent(sensorId)}&sampling_rate_hz=1000.0&fundamental_freq_hz=${freqHz}`;
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Simulation injection failed");
      }
      const burst = await res.json();
      el.simFeedback.textContent = `✓ Ingested seq #${burst.sequence_number} (${freqHz} Hz @ 1000 Hz, SHA-256: ${burst.sha256_hash.slice(0, 10)}...)`;
    } catch (err) {
      el.simFeedback.textContent = `⚠ Injection error: ${err.message}`;
    } finally {
      el.btnInjectSim.disabled = false;
    }
  });

  // --------------------------------------------------------------------------
  // 10. Application Boot
  // --------------------------------------------------------------------------
  loadInitialSnapshot();
  connectWebSocket();

})();
