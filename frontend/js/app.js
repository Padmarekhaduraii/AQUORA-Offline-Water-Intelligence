/**
 * AQUORA - Real-Data Offline Water Intelligence Platform
 * Production Modular Dashboard Controller
 */

document.addEventListener("DOMContentLoaded", async () => {
  // Initialize IndexedDB local storage
  if (window.aquoraStorage) {
    await window.aquoraStorage.init();
  }

  // DOM References: Status & Connectivity
  const dotGateway = document.getElementById("dotGateway");
  const textGateway = document.getElementById("textGateway");
  const dotInternet = document.getElementById("dotInternet");
  const textInternet = document.getElementById("textInternet");
  const pendingSyncCount = document.getElementById("pendingSyncCount");
  const textLastUpdated = document.getElementById("textLastUpdated");
  const alertsBanner = document.getElementById("alertsBanner");
  const alertContent = document.getElementById("alertContent");

  // Arrival Elements
  const arrivalStatusBadge = document.getElementById("arrivalStatusBadge");
  const arrivalMainTime = document.getElementById("arrivalMainTime");
  const arrivalUncertaintyLabel = document.getElementById("arrivalUncertaintyLabel");
  const arrivalTravelTime = document.getElementById("arrivalTravelTime");
  const confidenceBar = document.getElementById("confidenceBar");
  const confidencePercent = document.getElementById("confidencePercent");
  const arrivalSurgeMag = document.getElementById("arrivalSurgeMag");
  const arrivalCalcTime = document.getElementById("arrivalCalcTime");
  const arrivalExplanationText = document.getElementById("arrivalExplanationText");
  const arrivalSourceModeTag = document.getElementById("arrivalSourceModeTag");
  const confidenceExplanationNote = document.getElementById("confidenceExplanationNote");
  const confidenceBreakdownDetails = document.getElementById("confidenceBreakdownDetails");

  // Chart & Sensors
  const sensorNodesList = document.getElementById("sensorNodesList");
  const sensorLastRefresh = document.getElementById("sensorLastRefresh");
  const chartPills = document.querySelectorAll(".filter-pill[data-filter]");

  // Reservoirs & Irrigation
  const reservoirProviderSelect = document.getElementById("reservoirProviderSelect");
  const reservoirTableBody = document.getElementById("reservoirTableBody");
  const btnRefreshReservoirs = document.getElementById("btnRefreshReservoirs");
  const irrigationSchedulesList = document.getElementById("irrigationSchedulesList");
  const btnRecalcIrrigation = document.getElementById("btnRecalcIrrigation");

  // Weather Elements
  const weatherTemp = document.getElementById("weatherTemp");
  const weatherLoc = document.getElementById("weatherLoc");
  const weatherPrecip = document.getElementById("weatherPrecip");
  const weatherHumidity = document.getElementById("weatherHumidity");
  const weatherWind = document.getElementById("weatherWind");
  const weatherSource = document.getElementById("weatherSource");
  const weatherFreshness = document.getElementById("weatherFreshness");

  // Event Log
  const eventLogContainer = document.getElementById("eventLogContainer");
  const logFilterPills = document.querySelectorAll(".filter-pill[data-log-filter]");

  // Modals & Controls
  const btnManualSync = document.getElementById("btnManualSync");
  const btnOpenSettings = document.getElementById("btnOpenSettings");
  const settingsModal = document.getElementById("settingsModal");
  const btnCloseSettingsModal = document.getElementById("btnCloseSettingsModal");
  const settingsForm = document.getElementById("settingsForm");
  const inputApiBaseUrl = document.getElementById("inputApiBaseUrl");

  const btnOpenInjector = document.getElementById("btnOpenInjector");
  const telemetryModal = document.getElementById("telemetryModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const btnInjectSurge = document.getElementById("btnInjectSurge");
  const btnInjectDry = document.getElementById("btnInjectDry");
  const customReadingForm = document.getElementById("customReadingForm");

  const nodeDetailModal = document.getElementById("nodeDetailModal");
  const btnCloseNodeModal = document.getElementById("btnCloseNodeModal");
  const nodeModalBody = document.getElementById("nodeModalBody");
  const nodeModalTitle = document.getElementById("nodeModalTitle");

  // Initialize Interactive Canal Telemetry Chart
  let canalChart = null;
  if (window.AquoraCanalChart) {
    canalChart = new window.AquoraCanalChart("canalChartContainer");
  }

  // Active state filters
  let currentLogFilter = "ALL";
  let activeAlertsCache = [];
  let currentNodesCache = [];
  let pollIntervalMs = 8000;
  let pollTimer = null;
  let socket = null;

  // --- 1. Dual-Connectivity & Heartbeat Diagnostic ---
  async function updateConnectivityStatus() {
    const status = await window.aquoraApi.checkDualConnectivity();

    // Gateway (LAN / Localhost)
    if (status.gateway_connected) {
      dotGateway.className = "status-dot green";
      textGateway.textContent = "GATEWAY: LOCAL ONLINE";
    } else {
      dotGateway.className = "status-dot red";
      textGateway.textContent = "GATEWAY: OFFLINE (CHECK LOCAL HOST)";
    }

    // Internet (WAN)
    if (status.internet_connected) {
      dotInternet.className = "status-dot green";
      textInternet.textContent = "INTERNET: ACTIVE";
    } else {
      dotInternet.className = "status-dot red";
      textInternet.textContent = "INTERNET: OFFLINE (STANDALONE MESH)";
    }

    // Last Update Time
    if (status.last_update) {
      const timeStr = status.last_update.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      textLastUpdated.textContent = `Updated: ${timeStr}`;
    }
  }

  // --- 2. WebSocket Real-Time Telemetry Stream ---
  function initWebSocket() {
    try {
      const wsUrl = window.aquoraApi.getWebSocketUrl();
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.info("[AQUORA-WS] Connected to local telemetry stream:", wsUrl);
        dotGateway.className = "status-dot green";
      };

      socket.onmessage = async (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "NEW_READING" && msg.reading) {
            console.info("[AQUORA-WS-RX] Live packet:", msg.reading);
            // Save in IndexedDB
            if (window.aquoraStorage) {
              await window.aquoraStorage.put("sensor_readings", msg.reading);
            }
            // Trigger visual updates immediately
            await loadArrivalEstimate();
            await loadSensorNodes();
            await refreshChartTelemetry();
            await loadAlerts();
            textLastUpdated.textContent = `Updated: ${new Date().toLocaleTimeString()} (LoRa Push)`;
          }
        } catch (e) {
          console.warn("WebSocket parse error:", e);
        }
      };

      socket.onclose = () => {
        console.warn("[AQUORA-WS] Stream closed. Reconnecting in 5s...");
        setTimeout(initWebSocket, 5000);
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch (err) {
      console.warn("WebSocket setup error (relying on periodic polling):", err);
    }
  }

  // --- 3. Hydrodynamic Canal Water Arrival ---
  async function loadArrivalEstimate() {
    try {
      const { data, cached } = await window.aquoraApi.getArrivalEstimate();
      if (!data) return;

      arrivalStatusBadge.className = "arrival-status-badge";
      if (data.status === "SUFFICIENT_DATA" || data.status === "SURGE_IN_PROGRESS") {
        arrivalStatusBadge.classList.add("sufficient");
        arrivalStatusBadge.textContent = data.status === "SURGE_IN_PROGRESS" ? "FLOW SUSTAINED" : "SURGE IN PROGRESS";
      } else if (data.status === "NO_FLOW_DETECTED") {
        arrivalStatusBadge.classList.add("dry");
        arrivalStatusBadge.textContent = "NO FLOW / DRY CANAL";
      } else {
        arrivalStatusBadge.classList.add("insufficient");
        arrivalStatusBadge.textContent = "INSUFFICIENT DATA";
      }

      // Source Mode Provenance Tag
      if (arrivalSourceModeTag) {
        if (data.telemetry_source_mode === "SIMULATED_TEST_RUN") {
          arrivalSourceModeTag.className = "tag sim-warning-tag";
          arrivalSourceModeTag.textContent = "⚠️ SIMULATED TEST RUN";
        } else if (data.telemetry_source_mode === "PHYSICAL_GROUND_TRUTH") {
          arrivalSourceModeTag.className = "tag physical-ground-truth-tag";
          arrivalSourceModeTag.textContent = "🟢 PHYSICAL GROUND TRUTH";
        } else {
          arrivalSourceModeTag.className = "tag no-data-tag";
          arrivalSourceModeTag.textContent = "⚪ NO TELEMETRY";
        }
      }

      // Estimated Arrival Time Window
      if (data.estimated_arrival_time && data.data_sufficiency_met) {
        const arrDate = new Date(data.estimated_arrival_time);
        arrivalMainTime.textContent = arrDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const uncert = data.uncertainty_range_hours ? `±${data.uncertainty_range_hours} hrs` : "";
        arrivalUncertaintyLabel.textContent = `Estimated Arrival Window (${uncert} uncertainty)${cached ? ' [CACHED]' : ''}`;
      } else if (data.status === "NO_FLOW_DETECTED") {
        arrivalMainTime.textContent = "NO FLOW";
        arrivalUncertaintyLabel.textContent = "Canal bed is dry at upstream intake sluice";
      } else {
        arrivalMainTime.textContent = "--:--";
        arrivalUncertaintyLabel.textContent = "Awaiting sufficient physical sensor history";
      }

      arrivalTravelTime.textContent = data.travel_time_hours !== null ? `${data.travel_time_hours} hrs` : "--";

      // Confidence Score & Rubric Explanation
      if (data.data_sufficiency_met && data.confidence_percent !== null) {
        confidencePercent.textContent = `${data.confidence_percent}%`;
        confidenceBar.style.width = `${Math.min(100, data.confidence_percent)}%`;
        if (confidenceExplanationNote) {
          confidenceExplanationNote.textContent = data.confidence_explanation || "Mathematically derived from hydraulics";
        }

        if (confidenceBreakdownDetails && data.confidence_score_breakdown) {
          const b = data.confidence_score_breakdown;
          confidenceBreakdownDetails.innerHTML = `
            <div class="confidence-breakdown-grid">
              <div class="conf-item">
                <span class="conf-title">1. Telemetry Freshness</span>
                <span class="conf-score">${b.telemetry_freshness?.score || 0} / ${b.telemetry_freshness?.max || 35} pts</span>
                <small class="conf-sub">Sensor age: ${b.telemetry_freshness?.latest_age_minutes || 0}m</small>
              </div>
              <div class="conf-item">
                <span class="conf-title">2. Wave Trend Stability</span>
                <span class="conf-score">${b.wave_trend_stability?.score || 0} / ${b.wave_trend_stability?.max || 35} pts</span>
                <small class="conf-sub">${b.wave_trend_stability?.confirming_readings || 0} sequential readings</small>
              </div>
              <div class="conf-item">
                <span class="conf-title">3. Channel Calibration</span>
                <span class="conf-score">${b.hydraulic_calibration?.score || 0} / ${b.hydraulic_calibration?.max || 30} pts</span>
                <small class="conf-sub">Manning n=${b.hydraulic_calibration?.manning_roughness || 0.028} (${b.hydraulic_calibration?.reach_distance_km || 0} km)</small>
              </div>
            </div>
          `;
        }
      } else {
        // Unsupported confidence score removed when sufficiency is unmet
        confidencePercent.textContent = "N/A";
        confidenceBar.style.width = "0%";
        if (confidenceExplanationNote) {
          confidenceExplanationNote.textContent = data.confidence_explanation || "Confidence score withheld: Sufficiency criteria unmet";
        }
        if (confidenceBreakdownDetails) {
          if (data.unmet_sufficiency_requirements && data.unmet_sufficiency_requirements.length > 0) {
            confidenceBreakdownDetails.innerHTML = `
              <div class="unmet-requirements-list">
                <strong>⚠️ Documented Data-Sufficiency Requirements Unmet:</strong>
                <ul>
                  ${data.unmet_sufficiency_requirements.map(req => `<li>${req}</li>`).join("")}
                </ul>
              </div>
            `;
          } else {
            confidenceBreakdownDetails.innerHTML = "";
          }
        }
      }

      arrivalSurgeMag.textContent = data.upstream_surge_magnitude_cm !== null ? `+${data.upstream_surge_magnitude_cm} cm` : "--";

      const calcDate = new Date(data.calculated_at);
      arrivalCalcTime.textContent = calcDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      arrivalExplanationText.textContent = (cached ? "[OFFLINE CACHED] " : "") + (data.explanation || "No explanation provided.");

    } catch (err) {
      console.warn("Error loading arrival estimate:", err);
    }
  }

  // --- 4. Canal Sensor Nodes ---
  async function loadSensorNodes() {
    try {
      const { data, cached } = await window.aquoraApi.getNodes();
      currentNodesCache = data;
      sensorLastRefresh.textContent = cached ? "Cached Offline" : `Live: ${new Date().toLocaleTimeString()}`;

      if (data.length === 0) {
        sensorNodesList.innerHTML = `<div class="loading-placeholder">No canal sensor nodes registered yet.</div>`;
        return;
      }

      sensorNodesList.innerHTML = data.map(n => {
        const isOffline = n.is_disconnected || n.is_stale;
        const stateClass = isOffline ? "disconnected" : "live";
        const stateLabel = isOffline ? "DISCONNECTED / STALE" : "LIVE LORA";
        const depth = n.current_water_level_cm !== null ? n.current_water_level_cm.toFixed(1) : "--";
        const fillHeight = n.current_water_level_cm !== null ? Math.min(100, Math.max(5, (n.current_water_level_cm / n.max_depth_cm) * 100)) : 0;

        // Observation and Gateway receipt timestamps
        let obsTimeStr = "Never";
        if (n.last_observation_timestamp) {
          obsTimeStr = new Date(n.last_observation_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } else if (n.last_seen_at) {
          obsTimeStr = new Date(n.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        let gatewayRxStr = "Never";
        if (n.last_gateway_receipt_timestamp) {
          gatewayRxStr = new Date(n.last_gateway_receipt_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } else if (n.last_seen_at) {
          gatewayRxStr = new Date(n.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        // Provenance badge and descriptive subtext
        let provenanceTag = "";
        let depthSubtext = "";
        if (n.current_water_level_provenance === "SIMULATED" || n.current_water_level_is_simulated) {
          provenanceTag = `<span class="tag sim-warning-tag">⚠️ SIMULATED TEST DATA</span>`;
          depthSubtext = `⚠️ Injected test reading (Not physical sensor measurement)`;
        } else if (n.current_water_level_provenance === "PHYSICAL") {
          provenanceTag = `<span class="tag physical-ground-truth-tag">🟢 PHYSICAL SENSOR</span>`;
          depthSubtext = `Ground truth physical reading`;
        } else {
          provenanceTag = `<span class="tag no-data-tag">⚪ NO TELEMETRY</span>`;
          depthSubtext = `Awaiting sensor transmission`;
        }

        const freshClass = (n.freshness_status || "FRESH").toLowerCase();

        return `
          <div class="sensor-node-card" onclick="openNodeDiagnostics('${n.id}')" tabindex="0" role="button" aria-label="Inspect ${n.name} diagnostics">
            <div class="node-card-top">
              <div>
                <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.25rem;">
                  ${provenanceTag}
                  <span class="node-state-badge ${stateClass}">${stateLabel}</span>
                </div>
                <div class="node-name">${n.name}</div>
                <div class="node-reach">${n.canal_name} • ${n.reach_segment} (${n.distance_from_head_km} km)</div>
              </div>
            </div>

            <div class="node-depth-visual">
              <div class="depth-bar-outer" title="Water Level: ${depth} cm / Max: ${n.max_depth_cm} cm">
                <div class="depth-bar-fill" style="height: ${fillHeight}%;"></div>
              </div>
              <div class="depth-numbers">
                <div class="depth-val-huge">${depth} <span class="depth-unit">cm</span></div>
                <div class="depth-subtext">${depthSubtext}</div>
              </div>
            </div>

            <div class="node-timestamps-grid">
              <div class="node-timestamp-item">
                <span>Observed:</span>
                <strong>${obsTimeStr}</strong>
              </div>
              <div class="node-timestamp-item">
                <span>Gateway Rx:</span>
                <strong>${gatewayRxStr}</strong>
              </div>
              <div class="node-timestamp-item">
                <span>Source ID:</span>
                <strong>${n.id}</strong>
              </div>
              <div class="node-timestamp-item">
                <span>Freshness:</span>
                <strong class="freshness-text ${freshClass}">${n.freshness_status || 'LIVE'}</strong>
              </div>
            </div>
          </div>
        `;
      }).join("");

    } catch (err) {
      console.warn("Error loading sensor nodes:", err);
    }
  }

  // --- 5. Chart Telemetry Feeder ---
  async function refreshChartTelemetry() {
    if (!canalChart || currentNodesCache.length === 0) return;
    for (const node of currentNodesCache) {
      const { data } = await window.aquoraApi.getNodeHistory(node.id, 40);
      if (data && data.length > 0) {
        canalChart.setReadings(node.id, data);
      }
    }
  }

  // Chart node filter pills
  chartPills.forEach(pill => {
    pill.addEventListener("click", () => {
      chartPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      if (canalChart) {
        canalChart.setFilter(pill.getAttribute("data-filter"));
      }
    });
  });

  // --- 6. Verified Official Reservoirs ---
  async function loadReservoirs() {
    try {
      const provider = reservoirProviderSelect.value;
      const { data, cached } = await window.aquoraApi.getReservoirs(provider);

      if (data.length === 0) {
        reservoirTableBody.innerHTML = `<tr><td colspan="8" class="text-center">No official records available.</td></tr>`;
        return;
      }

      reservoirTableBody.innerHTML = data.map(item => {
        let fBadgeClass = "fresh";
        let displayFreshness = item.freshness_status;

        if (cached) {
          fBadgeClass = "stale";
          displayFreshness = "OFFICIAL - CACHED";
        } else if (item.freshness_status.includes("UNAVAILABLE") || item.freshness_status.includes("NO_PUBLIC_FEED")) {
          fBadgeClass = "unavailable";
          displayFreshness = "FEED UNAVAILABLE (GOV PORTAL)";
        } else if (item.freshness_status.includes("STALE") || item.freshness_status.includes("CACHED")) {
          fBadgeClass = "stale";
          displayFreshness = "OFFICIAL - CACHED";
        } else {
          fBadgeClass = "fresh";
          displayFreshness = "OFFICIAL - LIVE";
        }

        const sourceShort = item.provider_name === "tn_agriculture" ? "TN Agri (ARS)" : "Chennai Flood Monitor";

        return `
          <tr>
            <td>
              <strong>${item.reservoir_name}</strong>
              <div style="font-size: 0.68rem; color: var(--text-muted);">Basin Observation (Not Canal Arrival)</div>
            </td>
            <td>
              <div>${sourceShort}</div>
              <small style="color: var(--text-muted); font-size: 0.7rem;">Observed: ${item.observation_date}</small>
            </td>
            <td>${item.current_level_ft !== null ? item.current_level_ft.toFixed(2) : "--"}</td>
            <td>${item.full_depth_ft !== null ? item.full_depth_ft.toFixed(1) : "--"}</td>
            <td>${item.current_storage_mcft !== null ? item.current_storage_mcft.toLocaleString() : "--"}</td>
            <td>${item.inflow_cusecs !== null ? item.inflow_cusecs.toLocaleString() : "--"}</td>
            <td>${item.outflow_cusecs !== null ? item.outflow_cusecs.toLocaleString() : "--"}</td>
            <td><span class="freshness-badge ${fBadgeClass}">${displayFreshness}</span></td>
          </tr>
        `;
      }).join("");

    } catch (err) {
      console.warn("Error loading reservoirs:", err);
      reservoirTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-warning">Offline Standby: Official portal unreachable. Local cache active.</td></tr>`;
    }
  }

  // --- 7. Offline Irrigation Schedules ---
  async function loadIrrigationSchedules() {
    try {
      const { data } = await window.aquoraApi.getIrrigationSchedules();
      if (data.length === 0) {
        irrigationSchedulesList.innerHTML = `<div class="loading-placeholder">No active turns scheduled.</div>`;
        return;
      }

      irrigationSchedulesList.innerHTML = data.map(s => {
        const dt = new Date(s.recommended_start);
        const timeStr = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const isHold = s.status === "STANDBY_NO_WATER";
        const statusBadge = isHold 
          ? `<span style="color: var(--amber-400); font-weight: 700; font-size: 0.72rem;">[STANDBY: DRY CANAL]</span>`
          : `<span style="color: var(--emerald-400); font-weight: 700; font-size: 0.72rem;">[PLANNED TURN]</span>`;

        return `
          <div class="schedule-card-item">
            <div class="sched-left">
              <div class="sched-title">${s.zone_name} ${statusBadge}</div>
              <div class="sched-crop">${s.crop_type} • ${(s.water_volume_liters / 1000).toFixed(0)}k Liters required</div>
              <div class="sched-reason">${s.trigger_reason}</div>
            </div>
            <div class="sched-right">
              <div class="sched-time">${timeStr}</div>
              <div class="sched-dur">${s.recommended_duration_minutes} mins window</div>
            </div>
          </div>
        `;
      }).join("");

    } catch (err) {
      console.warn("Error loading irrigation schedules:", err);
    }
  }

  // --- 8. Supporting Weather Context ---
  async function loadWeatherContext() {
    try {
      const w = await window.aquoraApi.getWeatherContext();
      if (!w) return;

      weatherTemp.textContent = w.temperature_c !== null ? `${w.temperature_c.toFixed(1)}°C` : "--°C";
      weatherLoc.textContent = w.location;
      weatherPrecip.textContent = w.precipitation_mm !== null ? `${w.precipitation_mm} mm` : "0.0 mm";
      weatherHumidity.textContent = w.humidity_percent !== null ? `${w.humidity_percent}%` : "--%";
      weatherWind.textContent = w.wind_speed_kmh !== null ? `${w.wind_speed_kmh} km/h` : "-- km/h";
      weatherSource.textContent = w.source;
      weatherFreshness.textContent = w.freshness_status;

    } catch (err) {
      console.warn("Error loading weather:", err);
    }
  }

  // --- 9. System Alerts & Warnings ---
  async function loadAlerts() {
    try {
      const { data } = await window.aquoraApi.getAlerts();
      activeAlertsCache = data;

      const unacked = data.filter(a => !a.is_acknowledged);
      if (unacked.length > 0) {
        alertsBanner.style.display = "flex";
        alertContent.innerHTML = unacked.map(a => `
          <div class="alert-item">
            <div>
              <span class="alert-title">[${a.alert_type}]</span>
              <span>${a.message}</span>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="acknowledgeAlertItem(${a.id})" aria-label="Acknowledge alert ${a.title}">Acknowledge</button>
          </div>
        `).join("");
      } else {
        alertsBanner.style.display = "none";
      }

      renderEventLog();

    } catch (err) {
      console.warn("Error loading alerts:", err);
    }
  }

  window.acknowledgeAlertItem = async function(id) {
    try {
      await window.aquoraApi.acknowledgeAlert(id);
      loadAlerts();
    } catch (e) {
      console.error(e);
    }
  };

  // --- 10. Operational Event Log ---
  function renderEventLog() {
    if (!eventLogContainer) return;

    let items = [...activeAlertsCache];
    if (currentLogFilter !== "ALL") {
      items = items.filter(i => i.severity === currentLogFilter);
    }

    if (items.length === 0) {
      eventLogContainer.innerHTML = `<div class="chart-empty-state">No events matching severity "${currentLogFilter}".</div>`;
      return;
    }

    eventLogContainer.innerHTML = items.map(e => {
      let severityClass = "log-info";
      if (e.severity === "CRITICAL") severityClass = "log-crit";
      else if (e.severity === "WARNING") severityClass = "log-warn";

      const timeStr = new Date(e.created_at).toLocaleTimeString();

      return `
        <div class="event-log-entry ${severityClass}">
          <div>
            <strong>[${e.severity}] ${e.title}:</strong>
            <span>${e.message}</span>
          </div>
          <span class="event-time">${timeStr}</span>
        </div>
      `;
    }).join("");
  }

  logFilterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      logFilterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentLogFilter = pill.getAttribute("data-log-filter");
      renderEventLog();
    });
  });

  // --- 11. Sync Status ---
  async function loadSyncStatus() {
    try {
      const s = await window.aquoraApi.getSyncStatus();
      pendingSyncCount.textContent = s.pending_sensor_readings;
    } catch (err) {
      console.warn("Error loading sync status:", err);
    }
  }

  // --- 12. Station Diagnostics Modal ---
  window.openNodeDiagnostics = async function(nodeId) {
    const node = currentNodesCache.find(n => n.id === nodeId);
    if (!node) return;

    nodeModalTitle.textContent = `${node.name} (${node.id})`;
    nodeDetailModal.style.display = "flex";

    const { data: readings } = await window.aquoraApi.getNodeHistory(nodeId, 25);
    const latest = readings && readings.length > 0 ? readings[0] : null;

    const batt = latest && latest.battery_voltage ? `${latest.battery_voltage.toFixed(2)}V` : "--";
    const rssi = latest && latest.rssi_dbm ? `${latest.rssi_dbm} dBm` : "--";
    const depth = latest ? `${latest.water_level_cm.toFixed(1)} cm` : "--";

    // Distinguish simulation vs real physical ESP32 measurements
    const isSimulated = latest ? latest.is_simulated : (node.current_water_level_is_simulated || node.current_water_level_provenance === "SIMULATED");
    const bannerHtml = isSimulated
      ? `<div class="sim-warning-banner">⚠️ THIS STATION'S TELEMETRY CONTAINS SIMULATED TEST DATA (NOT PHYSICAL HARDWARE MEASUREMENT)</div>`
      : `<div class="physical-ground-truth-banner">🟢 VERIFIED PHYSICAL ESP32 SENSOR GROUND TRUTH (LoRa Mesh)</div>`;

    // Observation and Gateway Receipt Timestamps
    const obsTimeStr = latest && latest.timestamp_recorded 
      ? new Date(latest.timestamp_recorded).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) 
      : (node.last_observation_timestamp ? new Date(node.last_observation_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "Never");
    
    const gatewayRxStr = latest && latest.timestamp_received 
      ? new Date(latest.timestamp_received).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) 
      : (node.last_gateway_receipt_timestamp ? new Date(node.last_gateway_receipt_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "Never");

    nodeModalBody.innerHTML = `
      ${bannerHtml}
      <div class="station-diagnostics-grid">
        <div class="diag-stat-card">
          <span class="diag-stat-title">Current Water Level</span>
          <span class="diag-stat-val">${depth}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">Station Source ID</span>
          <span class="diag-stat-val" style="font-size: 0.95rem;">${node.id}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">Sensor Observation Time</span>
          <span class="diag-stat-val" style="font-size: 0.95rem;">${obsTimeStr}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">Gateway Receipt Time</span>
          <span class="diag-stat-val" style="font-size: 0.95rem;">${gatewayRxStr}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">Freshness Status</span>
          <span class="diag-stat-val" style="font-size: 1rem;">${node.freshness_status || 'LIVE'}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">Reach Distance</span>
          <span class="diag-stat-val">${node.distance_from_head_km} km</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">ESP32 Battery Voltage</span>
          <span class="diag-stat-val">${batt}</span>
        </div>
        <div class="diag-stat-card">
          <span class="diag-stat-title">LoRa Signal Strength</span>
          <span class="diag-stat-val">${rssi}</span>
        </div>
      </div>

      <div class="form-group" style="margin-top: 1rem;">
        <label>Canal Geometry & Calibration</label>
        <p class="modal-note">
          Zero Datum Offset: <strong>${node.zero_datum_offset_cm} cm</strong> | 
          Max Bank Depth: <strong>${node.max_depth_cm} cm</strong> | 
          Coordinates: <strong>${node.latitude || 10.8350}°N, ${node.longitude || 78.8180}°E</strong>
        </p>
      </div>

      <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-top: 1rem;">
        Station Telemetry Packets & Provenance Audit
      </h4>
      <div class="table-responsive" style="max-height: 220px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Observation Time</th>
              <th>Gateway Rx</th>
              <th>Depth</th>
              <th>Battery</th>
              <th>RSSI</th>
              <th>Provenance</th>
            </tr>
          </thead>
          <tbody>
            ${(readings || []).map(r => `
              <tr>
                <td>${new Date(r.timestamp_recorded).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                <td>${new Date(r.timestamp_received || r.timestamp_recorded).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                <td><strong>${r.water_level_cm.toFixed(1)} cm</strong></td>
                <td>${r.battery_voltage ? r.battery_voltage.toFixed(2) + 'V' : '--'}</td>
                <td>${r.rssi_dbm ? r.rssi_dbm + 'dBm' : '--'}</td>
                <td>
                  <span class="tag ${r.is_simulated ? 'sim-warning-tag' : 'physical-ground-truth-tag'}">
                    ${r.is_simulated ? '⚠️ SIMULATED' : '🟢 PHYSICAL'}
                  </span>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  };

  btnCloseNodeModal.addEventListener("click", () => nodeDetailModal.style.display = "none");

  // --- 13. Settings Modal ---
  btnOpenSettings.addEventListener("click", () => {
    inputApiBaseUrl.value = window.aquoraApi.getBaseUrl();
    settingsModal.style.display = "flex";
  });

  btnCloseSettingsModal.addEventListener("click", () => settingsModal.style.display = "none");

  settingsForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const val = inputApiBaseUrl.value;
    window.aquoraApi.setBaseUrl(val);
    settingsModal.style.display = "none";
    alert(`Configuration saved. Using API Base: ${window.aquoraApi.getBaseUrl()}`);
    refreshAll();
  });

  // --- 14. Action Controls ---
  btnManualSync.addEventListener("click", async () => {
    btnManualSync.disabled = true;
    btnManualSync.innerHTML = `<span>Syncing...</span>`;
    try {
      const data = await window.aquoraApi.triggerSync();
      alert(`Cloud Sync Result:\n${data.message}`);
      loadSyncStatus();
    } catch (e) {
      alert(`Sync completed in local mode: ${e}`);
    } finally {
      btnManualSync.disabled = false;
      btnManualSync.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><span>Sync Cloud</span>`;
    }
  });

  btnRecalcIrrigation.addEventListener("click", async () => {
    btnRecalcIrrigation.disabled = true;
    try {
      await window.aquoraApi.recalculateIrrigation();
      await loadIrrigationSchedules();
    } catch (e) {
      console.error(e);
    } finally {
      btnRecalcIrrigation.disabled = false;
    }
  });

  btnRefreshReservoirs.addEventListener("click", loadReservoirs);
  reservoirProviderSelect.addEventListener("change", loadReservoirs);

  // --- 15. Test Telemetry Injector Modal ---
  btnOpenInjector.addEventListener("click", () => telemetryModal.style.display = "flex");
  btnCloseModal.addEventListener("click", () => telemetryModal.style.display = "none");

  // Keyboard Navigation: Escape key closes any active modal
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      telemetryModal.style.display = "none";
      settingsModal.style.display = "none";
      nodeDetailModal.style.display = "none";
    }
  });

  btnInjectSurge.addEventListener("click", async () => {
    btnInjectSurge.disabled = true;
    try {
      const now = Date.now();
      const readings = [
        { level: 10.0, time: new Date(now - 3600000 * 2).toISOString() },
        { level: 12.0, time: new Date(now - 3600000).toISOString() },
        { level: 55.0, time: new Date(now - 1800000).toISOString() },
        { level: 86.5, time: new Date(now).toISOString() }
      ];

      for (const r of readings) {
        await window.aquoraApi.ingestReading({
          node_id: "NODE-UPSTREAM-01",
          timestamp_recorded: r.time,
          water_level_cm: r.level,
          water_flow_rate_lps: r.level * 6.5,
          battery_voltage: 4.12,
          rssi_dbm: -75.0,
          snr_db: 9.5,
          is_simulated: true
        });
      }

      await window.aquoraApi.ingestReading({
        node_id: "NODE-DOWNSTREAM-02",
        timestamp_recorded: new Date().toISOString(),
        water_level_cm: 4.2,
        water_flow_rate_lps: 0.0,
        battery_voltage: 3.98,
        rssi_dbm: -79.0,
        snr_db: 8.2,
        is_simulated: true
      });

      telemetryModal.style.display = "none";
      await refreshAll();
    } catch (e) {
      alert("Error injecting surge scenario: " + e);
    } finally {
      btnInjectSurge.disabled = false;
    }
  });

  btnInjectDry.addEventListener("click", async () => {
    btnInjectDry.disabled = true;
    try {
      await window.aquoraApi.ingestReading({
        node_id: "NODE-UPSTREAM-01",
        timestamp_recorded: new Date().toISOString(),
        water_level_cm: 3.8,
        water_flow_rate_lps: 0.0,
        battery_voltage: 4.10,
        rssi_dbm: -74.0,
        snr_db: 9.0,
        is_simulated: true
      });
      await window.aquoraApi.ingestReading({
        node_id: "NODE-DOWNSTREAM-02",
        timestamp_recorded: new Date().toISOString(),
        water_level_cm: 3.5,
        water_flow_rate_lps: 0.0,
        battery_voltage: 3.95,
        rssi_dbm: -78.0,
        snr_db: 8.5,
        is_simulated: true
      });
      telemetryModal.style.display = "none";
      await refreshAll();
    } catch (e) {
      alert("Error injecting dry scenario: " + e);
    } finally {
      btnInjectDry.disabled = false;
    }
  });

  customReadingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const nodeId = document.getElementById("inputNodeId").value;
    const level = document.getElementById("inputWaterLevel").value;
    const batt = document.getElementById("inputBattery").value;
    const rssi = document.getElementById("inputRssi").value;

    try {
      await window.aquoraApi.ingestReading({
        node_id: nodeId,
        timestamp_recorded: new Date().toISOString(),
        water_level_cm: parseFloat(level),
        water_flow_rate_lps: parseFloat(level) * 6.5,
        battery_voltage: parseFloat(batt),
        rssi_dbm: parseFloat(rssi),
        snr_db: 9.0,
        is_simulated: true
      });
      telemetryModal.style.display = "none";
      await refreshAll();
    } catch (err) {
      alert("Failed to ingest reading: " + err);
    }
  });

  // --- 16. Unified Refresh & Periodic Loop ---
  async function refreshAll() {
    await updateConnectivityStatus();
    await loadArrivalEstimate();
    await loadSensorNodes();
    await refreshChartTelemetry();
    await loadReservoirs();
    await loadIrrigationSchedules();
    await loadWeatherContext();
    await loadAlerts();
    await loadSyncStatus();
  }

  // Initial execution
  await refreshAll();
  initWebSocket();

  // Periodic polling fallback
  pollTimer = setInterval(async () => {
    await updateConnectivityStatus();
    await loadArrivalEstimate();
    await loadSensorNodes();
    await refreshChartTelemetry();
    await loadAlerts();
    await loadSyncStatus();
  }, pollIntervalMs);
});
