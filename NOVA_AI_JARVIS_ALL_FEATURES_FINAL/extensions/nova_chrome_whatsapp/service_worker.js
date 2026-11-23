const API = "http://127.0.0.1:8765";
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function postResult(id, result) {
  try {
    await fetch(API + "/complete", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({id, result})
    });
  } catch (e) { console.error("NOVA bridge result error", e); }
}

async function getOrOpenWhatsAppTab() {
  const tabs = await chrome.tabs.query({});
  let tab = tabs.find(t => (t.url || "").startsWith("https://web.whatsapp.com/"));
  if (tab) {
    await chrome.tabs.update(tab.id, {active: true});
    if (tab.windowId != null) await chrome.windows.update(tab.windowId, {focused: true});
    return tab;
  }
  const active = await chrome.tabs.query({active: true, lastFocusedWindow: true});
  const windowId = active[0]?.windowId;
  return await chrome.tabs.create({url:"https://web.whatsapp.com/", active:true, ...(windowId ? {windowId} : {})});
}

async function executeCommand(command) {
  const tab = await getOrOpenWhatsAppTab();
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    try {
      const response = await chrome.tabs.sendMessage(tab.id, {type:"NOVA_WHATSAPP_SEND", receiver:command.receiver, message:command.message});
      if (response && response.done) return response.result;
    } catch (_) {
      // Content script may not be injected until WhatsApp finishes loading.
    }
    await sleep(1000);
  }
  return "NOVA could not connect to the WhatsApp tab. Confirm the NOVA WhatsApp extension is enabled and reload web.whatsapp.com. No message was sent.";
}

async function poll() {
  try {
    const response = await fetch(API + "/next", {cache:"no-store"});
    if (response.ok) {
      const command = await response.json();
      if (command && command.id) {
        let result;
        try { result = await executeCommand(command); }
        catch (e) { result = "WhatsApp bridge error: " + String(e); }
        await postResult(command.id, result);
      }
    }
  } catch (_) {}
  setTimeout(poll, 900);
}
poll();
