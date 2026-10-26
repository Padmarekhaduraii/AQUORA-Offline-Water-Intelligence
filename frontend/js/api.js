/**
 * AQUORA - Production API Client & Dual-Connectivity Manager
 * Manages configurable API base URL, health probing, and local caching fallback.
 */

class AquoraApiClient {
  constructor() {
    this.defaultBaseUrl = window.location.origin;
    this.storageKey = "aquora_api_base_url";
    this.gatewayKey = "aquora_live_lora_secret_key_2026";
    this.lastSuccessfulUpdate = null;
    this.isGatewayOnline = false;
    this.isInternetOnline = navigator.onLine;

    // Listen to browser network events
    window.addEventListener("online", () => this.isInternetOnline = true);
    window.addEventListener("offline", () => this.isInternetOnline = false);
  }

  getBaseUrl() {
    const custom = localStorage.getItem(this.storageKey);
    if (custom && custom.trim() !== "") {
      return custom.trim().replace(/\/+$/, "");
    }
    // Default to current host or localhost:8000
    if (window.location.protocol.startsWith("http")) {
      return window.location.origin;
    }
    return "http://127.0.0.1:8000";
  }

  setBaseUrl(url) {
    if (!url || url.trim() === "") {
      localStorage.removeItem(this.storageKey);
    } else {
      localStorage.setItem(this.storageKey, url.trim().replace(/\/+$/, ""));
    }
  }

  getWebSocketUrl() {
    const base = this.getBaseUrl();
    const isHttps = base.startsWith("https://");
    const wsProto = isHttps ? "wss://" : "ws://";
    const host = base.replace(/^https?:\/\//, "");
    return `${wsProto}${host}/api/v1/ws/telemetry`;
  }

  async fetchWithTimeout(endpoint, options = {}, timeoutMs = 6000) {
    const base = this.getBaseUrl();
    const url = `${base}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      
      this.lastSuccessfulUpdate = new Date();
      this.isGatewayOnline = true;
      return response;
    } catch (err) {
      clearTimeout(timeoutId);
      this.isGatewayOnline = false;
      throw err;
    }
  }

  // --- Dual-Connectivity Diagnostic ---
  async checkDualConnectivity() {
    let gatewayReachable = false;
    try {
      const res = await this.fetchWithTimeout("/api/v1/health", {}, 3000);
      if (res.ok) gatewayReachable = true;
    } catch (e) {
      gatewayReachable = false;
    }

    this.isGatewayOnline = gatewayReachable;
    this.isInternetOnline = navigator.onLine;

    return {
      gateway_connected: this.isGatewayOnline,
      internet_connected: this.isInternetOnline,
      last_update: this.lastSuccessfulUpdate
    };
  }

  // --- Sensor APIs ---
  async getNodes() {
    try {
      const res = await this.fetchWithTimeout("/api/v1/sensors/nodes");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Cache in IndexedDB
      if (window.aquoraStorage) {
        window.aquoraStorage.putBatch("sensor_nodes", data);
      }
      return { data, cached: false };
    } catch (err) {
      console.warn("API getNodes failed, serving from IndexedDB fallback:", err);
      const cached = window.aquoraStorage ? await window.aquoraStorage.getAll("sensor_nodes") : [];
      return { data: cached, cached: true };
    }
  }

  async getNodeHistory(nodeId, limit = 50) {
    try {
      const res = await this.fetchWithTimeout(`/api/v1/sensors/${nodeId}/history?limit=${limit}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (window.aquoraStorage) {
        window.aquoraStorage.putBatch("sensor_readings", data);
      }
      return { data, cached: false };
    } catch (err) {
      console.warn(`API getNodeHistory for ${nodeId} failed, reading cache:`, err);
      if (window.aquoraStorage) {
        const allReadings = await window.aquoraStorage.getAll("sensor_readings");
        const filtered = allReadings.filter(r => r.node_id === nodeId);
        return { data: filtered, cached: true };
      }
      return { data: [], cached: true };
    }
  }

  async ingestReading(payload) {
    const res = await this.fetchWithTimeout("/api/v1/sensors/ingest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.gatewayKey
      },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`Ingest failed: HTTP ${res.status}`);
    return await res.json();
  }

  // --- Official Reservoir APIs ---
  async getReservoirs(provider = null, date = null) {
    let endpoint = "/api/v1/official/reservoirs";
    const params = new URLSearchParams();
    if (provider) params.append("provider", provider);
    if (date) params.append("date", date);
    if (params.toString()) endpoint += `?${params.toString()}`;

    try {
      const res = await this.fetchWithTimeout(endpoint);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (window.aquoraStorage) {
        window.aquoraStorage.putBatch("reservoirs", data);
      }
      return { data, cached: false };
    } catch (err) {
      console.warn("API getReservoirs failed, reading cache:", err);
      const cached = window.aquoraStorage ? await window.aquoraStorage.getAll("reservoirs") : [];
      return { data: cached, cached: true };
    }
  }

  // --- Intelligence & Arrival APIs ---
  async getArrivalEstimate(targetId = "NODE-DOWNSTREAM-02", upstreamId = "NODE-UPSTREAM-01") {
    const endpoint = `/api/v1/intelligence/arrival-estimates?target_node_id=${targetId}&reference_upstream_node_id=${upstreamId}`;
    try {
      const res = await this.fetchWithTimeout(endpoint);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (window.aquoraStorage) {
        window.aquoraStorage.put("arrival_estimates", { id: "latest", ...data });
      }
      return { data, cached: false };
    } catch (err) {
      console.warn("API getArrivalEstimate failed, reading cache:", err);
      const cached = window.aquoraStorage ? await window.aquoraStorage.get("arrival_estimates", "latest") : null;
      return { data: cached, cached: true };
    }
  }

  async getWeatherContext(lat = null, lon = null) {
    let endpoint = "/api/v1/intelligence/weather-context";
    if (lat && lon) endpoint += `?lat=${lat}&lon=${lon}`;
    try {
      const res = await this.fetchWithTimeout(endpoint);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("API getWeatherContext failed:", err);
      return null;
    }
  }

  // --- Irrigation APIs ---
  async getIrrigationSchedules() {
    try {
      const res = await this.fetchWithTimeout("/api/v1/irrigation/schedules");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (window.aquoraStorage) {
        window.aquoraStorage.putBatch("irrigation_schedules", data);
      }
      return { data, cached: false };
    } catch (err) {
      console.warn("API getIrrigationSchedules failed, reading cache:", err);
      const cached = window.aquoraStorage ? await window.aquoraStorage.getAll("irrigation_schedules") : [];
      return { data: cached, cached: true };
    }
  }

  async recalculateIrrigation() {
    const res = await this.fetchWithTimeout("/api/v1/irrigation/recalculate", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  // --- Alerts APIs ---
  async getAlerts() {
    try {
      const res = await this.fetchWithTimeout("/api/v1/alerts");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (window.aquoraStorage) {
        window.aquoraStorage.putBatch("alerts", data);
      }
      return { data, cached: false };
    } catch (err) {
      console.warn("API getAlerts failed, reading cache:", err);
      const cached = window.aquoraStorage ? await window.aquoraStorage.getAll("alerts") : [];
      return { data: cached, cached: true };
    }
  }

  async acknowledgeAlert(alertId) {
    const res = await this.fetchWithTimeout(`/api/v1/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  // --- Sync APIs ---
  async getSyncStatus() {
    const res = await this.fetchWithTimeout("/api/v1/sync/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  async triggerSync() {
    const res = await this.fetchWithTimeout("/api/v1/sync/trigger", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }
}

// Global API Client Singleton
window.aquoraApi = new AquoraApiClient();
