const state = {
  config: null,
  fields: new Map(),
  providers: [],
  localStatus: new Map(),
  modelOptions: new Map(),
  connectionResults: new Map(),
  testingProviders: new Set(),
  drafts: new Map(),
  activeView: "providers",
  providerFilter: "all",
  providerSearch: "",
  selectedProviderId: null,
};

const MASKED_SECRET = "********";
const VIEW_GROUPS = [
  {
    id: "providers",
    label: "Providers",
    title: "Providers",
    description: "Add a provider key, test access, and choose the default model.",
    sections: [],
  },
  {
    id: "model_config",
    label: "Model settings",
    title: "Model settings",
    description: "Control reasoning and gateway-hosted web tools.",
    sections: ["thinking", "web_tools"],
  },
  {
    id: "messaging",
    label: "Messaging",
    title: "Messaging",
    description: "Configure optional Discord, Telegram, and voice workflows.",
    sections: ["messaging", "voice"],
  },
  {
    id: "advanced",
    label: "Advanced",
    title: "Advanced",
    description: "Runtime, diagnostics, and smoke-test configuration.",
    sections: ["runtime", "diagnostics", "smoke"],
  },
];

const EXTRA_PROVIDER_FIELDS = {
  cloudflare: ["CLOUDFLARE_ACCOUNT_ID"],
};

const byId = (id) => document.getElementById(id);

function sourceLabel(source) {
  const labels = {
    default: "default",
    template: "template",
    repo_env: "repo .env",
    managed_env: "",
    explicit_env_file: "FREE_CODEX_ENV_FILE",
    process: "process env",
  };
  return Object.prototype.hasOwnProperty.call(labels, source) ? labels[source] : source;
}

function sourceText(field) {
  const parts = [];
  const label = sourceLabel(field.source);
  if (label) parts.push(label);
  if (field.locked) parts.push("locked");
  return parts.join(" · ");
}

function statusClass(status) {
  if (["configured", "reachable", "running"].includes(status)) return "ok";
  if (["offline", "error"].includes(status)) return "error";
  return "neutral";
}

function providerMonogram(provider) {
  const words = (provider.display_name || provider.provider_id)
    .replace(/[^a-zA-Z0-9 ]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function providerDescription(provider) {
  return provider.kind === "local"
    ? `Local inference through ${provider.display_name}`
    : `Cloud inference via ${provider.display_name}`;
}

function providerIsConfigured(provider) {
  if (["configured", "reachable", "running"].includes(provider.status)) return true;
  const fieldKey = provider.kind === "local" ? provider.base_url_env : provider.credential_env;
  return Boolean(fieldKey && state.drafts.get(fieldKey));
}

function providerStatus(provider) {
  const fieldKey = provider.kind === "local" ? provider.base_url_env : provider.credential_env;
  if (fieldKey && state.drafts.has(fieldKey)) {
    return { status: "unknown", label: "Ready to test" };
  }
  return { status: provider.status, label: provider.label };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function load() {
  showMessage("Loading configuration");
  const config = await api("/admin/api/config");
  state.config = config;
  state.fields = new Map(config.fields.map((field) => [field.key, field]));
  state.providers = config.provider_status;
  state.drafts.clear();
  chooseInitialProvider();
  renderNav();
  renderProviderList();
  renderActiveView();
  byId("providerCount").textContent = `${state.providers.length} available`;
  byId("configPath").textContent = config.paths.managed;
  updateDirtyState();
  await refreshLocalStatus();
  showMessage("");
}

function chooseInitialProvider() {
  if (state.providers.some((provider) => provider.provider_id === state.selectedProviderId)) {
    return;
  }
  const model = state.fields.get("MODEL")?.value || "";
  const modelProvider = model.split("/")[0];
  const preferred =
    state.providers.find((provider) => provider.provider_id === modelProvider) ||
    state.providers.find(providerIsConfigured) ||
    state.providers[0];
  state.selectedProviderId = preferred?.provider_id || null;
}

function renderNav() {
  const nav = byId("sectionNav");
  nav.innerHTML = "";
  VIEW_GROUPS.forEach((view) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-link${view.id === state.activeView ? " active" : ""}`;
    button.dataset.view = view.id;
    button.textContent = view.label;
    if (view.id === state.activeView) button.setAttribute("aria-current", "page");
    button.addEventListener("click", () => setActiveView(view.id));
    nav.appendChild(button);
  });
}

function setActiveView(viewId) {
  state.activeView = VIEW_GROUPS.some((view) => view.id === viewId) ? viewId : "providers";
  renderNav();
  renderActiveView();
  document.querySelector(".workspace-view:not([hidden])")?.scrollTo({ top: 0 });
}

function renderActiveView() {
  const providerView = byId("providerWorkspace");
  const settingsView = byId("settingsWorkspace");
  const view = VIEW_GROUPS.find((item) => item.id === state.activeView) || VIEW_GROUPS[0];
  byId("headerSection").textContent = view.title;
  if (view.id === "providers") {
    providerView.hidden = false;
    settingsView.hidden = true;
    renderProviderDetail();
    return;
  }
  providerView.hidden = true;
  settingsView.hidden = false;
  renderSettingsView(view);
}

function filteredProviders() {
  const search = state.providerSearch.trim().toLowerCase();
  return state.providers.filter((provider) => {
    const matchesSearch =
      !search ||
      provider.display_name.toLowerCase().includes(search) ||
      provider.provider_id.toLowerCase().includes(search);
    if (!matchesSearch) return false;
    if (state.providerFilter === "configured") return providerIsConfigured(provider);
    if (state.providerFilter === "remote") return provider.kind === "remote";
    if (state.providerFilter === "local") return provider.kind === "local";
    return true;
  });
}

function renderProviderList() {
  const list = byId("providerList");
  list.innerHTML = "";
  const providers = filteredProviders();
  if (providers.length === 0) {
    const empty = document.createElement("div");
    empty.className = "provider-empty";
    empty.textContent = "No providers match this filter.";
    list.appendChild(empty);
    return;
  }
  providers.forEach((provider) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `provider-row${
      provider.provider_id === state.selectedProviderId ? " selected" : ""
    }`;
    button.dataset.providerId = provider.provider_id;
    button.setAttribute("aria-label", `Select ${provider.display_name}`);
    if (provider.provider_id === state.selectedProviderId) {
      button.setAttribute("aria-current", "true");
    }

    const monogram = document.createElement("span");
    monogram.className = "provider-monogram";
    monogram.textContent = providerMonogram(provider);

    const copy = document.createElement("span");
    copy.className = "provider-copy";
    const name = document.createElement("strong");
    name.textContent = provider.display_name;
    const kind = document.createElement("small");
    kind.textContent = provider.kind === "local" ? "Local" : "Cloud";
    copy.append(name, kind);

    const currentStatus = providerStatus(provider);
    const status = document.createElement("span");
    status.className = `provider-row-status ${statusClass(currentStatus.status)}`;
    status.textContent = currentStatus.label;

    button.append(monogram, copy, status);
    button.addEventListener("click", () => {
      state.selectedProviderId = provider.provider_id;
      state.activeView = "providers";
      renderNav();
      renderProviderList();
      renderActiveView();
    });
    list.appendChild(button);
  });
}

function selectedProvider() {
  return state.providers.find((provider) => provider.provider_id === state.selectedProviderId);
}

function renderProviderDetail() {
  const provider = selectedProvider();
  if (!provider) return;

  byId("selectedProviderIcon").textContent = providerMonogram(provider);
  byId("selectedProviderName").textContent = provider.display_name;
  byId("selectedProviderDescription").textContent = providerDescription(provider);

  const currentStatus = providerStatus(provider);
  const status = byId("selectedProviderStatus");
  status.className = `status-text ${statusClass(currentStatus.status)}`;
  status.textContent = currentStatus.label;

  const models = state.modelOptions.get(provider.provider_id) || [];
  byId("selectedProviderModels").textContent = models.length
    ? `${models.length} models available`
    : "Models not loaded";

  renderTestProviderButton(provider);

  renderCredential(provider);
  renderModel(provider);
  renderConnection(provider);
  renderProviderAdvanced(provider);
}

function renderTestProviderButton(provider) {
  const button = byId("testProviderButton");
  const testing = state.testingProviders.has(provider.provider_id);
  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = testing ? "↻" : "▷";
  button.disabled = testing;
  button.replaceChildren(
    icon,
    document.createTextNode(testing ? "Testing…" : "Test connection"),
  );
}

function renderCredential(provider) {
  const heading = byId("credentialHeading");
  const description = byId("credentialDescription");
  const link = byId("credentialLink");
  const container = byId("credentialField");
  const fieldKey = provider.kind === "local" ? provider.base_url_env : provider.credential_env;
  const field = state.fields.get(fieldKey);

  heading.textContent = provider.kind === "local" ? "Server address" : "API credential";
  description.textContent =
    provider.kind === "local"
      ? "Enter the URL of the local model server."
      : "Paste the API key supplied by this provider.";
  link.hidden = provider.kind === "local" || !provider.credential_url;
  if (!link.hidden) link.href = provider.credential_url;

  container.innerHTML = "";
  if (!field) {
    container.textContent = "This provider has no configurable credential field.";
    return;
  }
  container.appendChild(
    renderField(field, {
      label: provider.kind === "local" ? `${provider.display_name} URL` : "API key",
      description:
        provider.kind === "local"
          ? `Default: ${provider.default_base_url || provider.base_url}`
          : "Stored locally in ~/.free-codex/.env. Existing keys are never shown.",
      wide: true,
    }),
  );
}

function renderModel(provider) {
  const container = byId("modelField");
  const field = state.fields.get("MODEL");
  container.innerHTML = "";
  if (!field) return;
  const options = state.modelOptions.get(provider.provider_id) || [];
  syncModelDatalist(provider.provider_id);
  const currentProvider = (state.drafts.get("MODEL") || field.value || "").split("/")[0];
  const description = options.length
    ? `${options.length} models discovered. Choose one or type a provider-prefixed model ID.`
    : currentProvider === provider.provider_id
      ? "This is the current default. Test the connection to refresh available models."
      : `The current default belongs to ${currentProvider || "another provider"}. Test this provider, then choose a model.`;
  const wrapper = renderField(field, {
    label: "Provider-prefixed model",
    description,
    wide: true,
  });
  const input = wrapper.querySelector("input");
  if (input) input.setAttribute("list", "model-options");
  container.appendChild(wrapper);
}

function renderConnection(provider) {
  const endpoint = provider.kind === "local"
    ? currentFieldValue(state.fields.get(provider.base_url_env)) || provider.base_url
    : provider.default_base_url;
  byId("providerEndpoint").textContent = endpoint || "Endpoint unavailable";
  const result = state.connectionResults.get(provider.provider_id);
  const area = byId("connectionResult");
  if (!result) {
    area.className = "connection-result neutral";
    area.textContent = "Run a connection test to verify access and discover models.";
    return;
  }
  area.className = `connection-result ${result.ok ? "ok" : "error"}`;
  area.textContent = result.message;
}

function renderProviderAdvanced(provider) {
  const container = byId("providerAdvancedFields");
  container.innerHTML = "";
  const keys = [
    ...(EXTRA_PROVIDER_FIELDS[provider.provider_id] || []),
    ...(provider.proxy_env ? [provider.proxy_env] : []),
  ];
  keys
    .map((key) => state.fields.get(key))
    .filter(Boolean)
    .forEach((field) => container.appendChild(renderField(field)));
  byId("providerAdvanced").hidden = container.children.length === 0;
}

function renderSettingsView(view) {
  byId("settingsEyebrow").textContent = "Configuration";
  byId("settingsTitle").textContent = view.title;
  byId("settingsDescription").textContent = view.description;
  const container = byId("settingsSections");
  container.innerHTML = "";

  const sections = new Map(state.config.sections.map((section) => [section.id, section]));
  view.sections.forEach((sectionId) => {
    const section = sections.get(sectionId);
    const fields = state.config.fields.filter((field) => field.section === sectionId);
    if (!section || fields.length === 0) return;
    container.appendChild(renderSettingsSection(section, fields));
  });
}

function renderSettingsSection(section, fields) {
  const sectionElement = document.createElement("section");
  sectionElement.className = "settings-section";
  const header = document.createElement("div");
  header.className = "settings-section-header";
  const title = document.createElement("h2");
  title.textContent = section.label;
  const description = document.createElement("p");
  description.textContent = section.description;
  header.append(title, description);

  const grid = document.createElement("div");
  grid.className = "field-grid";
  fields.forEach((field) => grid.appendChild(renderField(field)));
  sectionElement.append(header, grid);

  if (fields.some((field) => field.advanced)) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "advanced-toggle";
    toggle.textContent = "Show advanced fields";
    toggle.addEventListener("click", () => {
      const showing = sectionElement.classList.toggle("show-advanced");
      toggle.textContent = showing ? "Hide advanced fields" : "Show advanced fields";
    });
    sectionElement.appendChild(toggle);
  }
  return sectionElement;
}

function renderField(field, overrides = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `field${field.advanced ? " advanced-field" : ""}${
    overrides.wide ? " wide" : ""
  }`;
  wrapper.dataset.field = field.key;

  if (field.type === "boolean") {
    const label = document.createElement("label");
    label.className = "checkbox-control";
    const text = document.createElement("span");
    text.textContent = overrides.label || field.label;
    const input = inputForField(field);
    label.append(text, input);
    wrapper.appendChild(label);
  } else {
    const label = document.createElement("label");
    label.htmlFor = `field-${field.key}`;
    const labelText = document.createElement("span");
    labelText.textContent = overrides.label || field.label;
    label.appendChild(labelText);
    const source = sourceText(field);
    if (source) {
      const sourceElement = document.createElement("span");
      sourceElement.className = "field-source";
      sourceElement.textContent = source;
      label.appendChild(sourceElement);
    }

    const shell = document.createElement("div");
    shell.className = `control-shell${field.secret ? " has-action" : ""}`;
    const input = inputForField(field);
    shell.appendChild(input);
    if (field.secret) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-button";
      toggle.textContent = "Show";
      toggle.setAttribute("aria-label", `Show ${overrides.label || field.label}`);
      toggle.addEventListener("click", () => {
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        toggle.textContent = showing ? "Show" : "Hide";
      });
      shell.appendChild(toggle);
    }
    wrapper.append(label, shell);
  }

  const descriptionText = overrides.description || field.description;
  if (descriptionText) {
    const description = document.createElement("div");
    description.className = "field-description";
    description.textContent = descriptionText;
    wrapper.appendChild(description);
  }
  return wrapper;
}

function inputForField(field) {
  let input;
  if (field.type === "boolean") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = currentFieldValue(field) === "true";
  } else if (field.type === "tri_boolean" || field.type === "select") {
    input = document.createElement("select");
    const options =
      field.type === "tri_boolean"
        ? [
            ["", "Inherit"],
            ["true", "Enabled"],
            ["false", "Disabled"],
          ]
        : field.options.map((value) => [value, value]);
    options.forEach(([value, label]) => input.appendChild(option(value, label)));
    input.value = currentFieldValue(field);
  } else if (field.type === "textarea") {
    input = document.createElement("textarea");
    input.value = currentFieldValue(field);
  } else {
    input = document.createElement("input");
    input.type = field.type === "number" ? "number" : "text";
    if (field.secret) {
      input.type = "password";
      input.placeholder = field.configured
        ? "Configured — enter a new value to replace"
        : "Paste key here";
      input.value = state.drafts.get(field.key) || "";
      input.autocomplete = "off";
    } else {
      input.value = currentFieldValue(field);
    }
  }

  input.id = `field-${field.key}`;
  input.dataset.key = field.key;
  input.dataset.original = field.value || "";
  input.dataset.secret = field.secret ? "true" : "false";
  input.dataset.configured = field.configured ? "true" : "false";
  input.disabled = field.locked;
  input.addEventListener("input", () => captureDraft(input));
  input.addEventListener("change", () => captureDraft(input));
  return input;
}

function option(value, label) {
  const optionElement = document.createElement("option");
  optionElement.value = value;
  optionElement.textContent = label;
  return optionElement;
}

function currentFieldValue(field) {
  if (!field) return "";
  if (state.drafts.has(field.key)) return String(state.drafts.get(field.key));
  if (field.secret) return "";
  return String(field.value || "");
}

function inputValue(input) {
  if (input.type === "checkbox") return input.checked ? "true" : "false";
  if (input.dataset.secret === "true" && input.dataset.configured === "true") {
    return input.value ? input.value : MASKED_SECRET;
  }
  return input.value;
}

function captureDraft(input) {
  const value = inputValue(input);
  if (value === input.dataset.original) {
    state.drafts.delete(input.dataset.key);
  } else {
    state.drafts.set(input.dataset.key, value);
  }
  const provider = selectedProvider();
  if (provider?.base_url_env === input.dataset.key) {
    byId("providerEndpoint").textContent = value || provider.default_base_url;
  }
  renderProviderList();
  updateDirtyState();
}

function changedValues() {
  return Object.fromEntries(state.drafts.entries());
}

function updateDirtyState() {
  const count = state.drafts.size;
  byId("dirtyState").textContent =
    count === 0 ? "No unsaved changes" : `${count} unsaved change${count === 1 ? "" : "s"}`;
  byId("applyButton").disabled = count === 0;
}

async function validate(showResult = true) {
  const result = await api("/admin/api/config/validate", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (showResult) showValidationResult(result);
  return result;
}

function showValidationResult(result) {
  if (result.valid) {
    showMessage("Configuration is valid", "ok");
  } else {
    showMessage(result.errors.join("; "), "error");
  }
}

async function apply() {
  const button = byId("applyButton");
  button.disabled = true;
  showMessage("Applying configuration");
  const result = await api("/admin/api/config/apply", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (!result.applied) {
    showValidationResult(result);
    updateDirtyState();
    return;
  }
  const restart = result.restart || {};
  if (restart.required && restart.automatic) {
    showMessage("Applied — restarting gateway", "ok");
    setTimeout(() => {
      window.location.href = restart.admin_url || "/admin";
    }, 1400);
    return;
  }
  const pending = restart.required ? restart.fields || [] : result.pending_fields || [];
  await load();
  showMessage(
    pending.length
      ? `Applied. Restart the gateway to use: ${pending.join(", ")}`
      : "Configuration applied",
    "ok",
  );
}

async function refreshLocalStatus() {
  const result = await api("/admin/api/providers/local-status");
  result.providers.forEach((localProvider) => {
    state.localStatus.set(localProvider.provider_id, localProvider);
    const provider = state.providers.find(
      (item) => item.provider_id === localProvider.provider_id,
    );
    if (!provider) return;
    provider.status = localProvider.status;
    provider.label = localProvider.label;
    provider.base_url = localProvider.base_url;
  });
  renderProviderList();
  if (state.activeView === "providers") renderProviderDetail();
}

async function testSelectedProvider() {
  const provider = selectedProvider();
  if (!provider) return;
  if (state.testingProviders.has(provider.provider_id)) return;
  state.testingProviders.add(provider.provider_id);
  renderProviderDetail();
  showMessage(`Testing ${provider.display_name}`);
  try {
    const result = await api(`/admin/api/providers/${provider.provider_id}/test`, {
      method: "POST",
      body: JSON.stringify({ values: changedValues() }),
    });
    if (result.ok) {
      state.modelOptions.set(provider.provider_id, result.models);
      provider.status = "reachable";
      provider.label = "Connected";
      state.connectionResults.set(provider.provider_id, {
        ok: true,
        message: `Connection verified · ${result.models.length} models available`,
      });
      showMessage(`${provider.display_name} connected`, "ok");
    } else {
      provider.status = "error";
      provider.label = "Connection failed";
      const detail = result.errors?.join("; ") || result.error_type;
      state.connectionResults.set(provider.provider_id, {
        ok: false,
        message: `Connection failed · ${detail}`,
      });
      showMessage(`${provider.display_name}: ${detail}`, "error");
    }
  } catch (error) {
    provider.status = "error";
    provider.label = "Connection failed";
    state.connectionResults.set(provider.provider_id, {
      ok: false,
      message: `Connection failed · ${error.message}`,
    });
    showMessage(error.message, "error");
  } finally {
    state.testingProviders.delete(provider.provider_id);
    renderProviderList();
    if (state.activeView === "providers") renderProviderDetail();
  }
}

function syncModelDatalist(providerId) {
  const datalist = byId("model-options");
  datalist.innerHTML = "";
  const models = state.modelOptions.get(providerId) || [];
  models
    .map((model) => `${providerId}/${model}`)
    .forEach((model) => datalist.appendChild(option(model, model)));
}

function showMessage(message, kind = "") {
  const area = byId("messageArea");
  area.textContent = message;
  area.className = `message-area ${kind}`.trim();
}

document.querySelectorAll(".filter-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.providerFilter = button.dataset.filter;
    document.querySelectorAll(".filter-button").forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    renderProviderList();
  });
});

byId("providerSearch").addEventListener("input", (event) => {
  state.providerSearch = event.target.value;
  renderProviderList();
});

document.addEventListener("keydown", (event) => {
  const target = event.target;
  const editing = target.matches("input, textarea, select");
  if (event.key === "/" && !editing) {
    event.preventDefault();
    byId("providerSearch").focus();
  }
});

byId("testProviderButton").addEventListener("click", testSelectedProvider);
byId("refreshModelsButton").addEventListener("click", testSelectedProvider);
byId("validateButton").addEventListener("click", () => validate(true));
byId("applyButton").addEventListener("click", apply);

load().catch((error) => showMessage(error.message, "error"));
