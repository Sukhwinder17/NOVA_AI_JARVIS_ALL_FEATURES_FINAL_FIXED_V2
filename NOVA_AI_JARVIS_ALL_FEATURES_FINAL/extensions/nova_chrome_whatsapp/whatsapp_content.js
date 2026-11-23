(() => {
  if (window.__novaWhatsAppBridgeInstalled) return;
  window.__novaWhatsAppBridgeInstalled = true;

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);

  function findSearch() {
    const selectors = [
      '[data-testid="chat-list-search"]',
      '[data-testid="chat-list-search"] [contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"][data-tab="3"]',
      'div[contenteditable="true"][aria-label*="Search"]',
      'input[placeholder*="Search"]'
    ];
    for (const selector of selectors) {
      const el = [...document.querySelectorAll(selector)].find(visible);
      if (el) return el;
    }
    return [...document.querySelectorAll('[contenteditable="true"],input')]
      .find(el => visible(el) && /search|new chat/i.test((el.getAttribute("aria-label") || "") + " " + (el.getAttribute("placeholder") || ""))) || null;
  }

  function setText(el, value) {
    el.focus();
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
      if (setter) setter.call(el, value); else el.value = value;
      el.dispatchEvent(new Event("input", {bubbles:true}));
    } else {
      el.textContent = value;
      el.dispatchEvent(new InputEvent("input", {bubbles:true, inputType:"insertText", data:value}));
    }
  }

  async function run(receiver, message) {
    const end = Date.now() + 180000;
    let search = null;
    while (Date.now() < end) {
      const body = (document.body?.innerText || "").toLowerCase();
      if (/scan the qr code|link with phone number/.test(body)) {
        await sleep(1200);
        continue; // Wait for the user to log in; no second browser is launched.
      }
      search = findSearch();
      if (search) break;
      await sleep(700);
    }
    if (!search) return "WhatsApp Web did not become ready. If it shows a QR code, log in and try again. No message was sent.";

    setText(search, receiver);
    await sleep(1300);

    const candidates = [...document.querySelectorAll('[role="listitem"], [data-testid*="cell-frame"], [role="option"]')].filter(visible);
    const wanted = receiver.trim().toLocaleLowerCase();
    let match = candidates.find(el => {
      const first = (el.innerText || "").trim().split("\n")[0].trim().toLocaleLowerCase();
      return first === wanted;
    });
    if (!match) return "No exact WhatsApp contact match found for '" + receiver + "'. No message was sent.";
    match.click();
    await sleep(900);

    const header = document.querySelector('#main header');
    const headerText = (header?.innerText || "").trim().toLocaleLowerCase();
    const headerTitle = [...(header?.querySelectorAll("[title]") || [])].map(el => el.getAttribute("title") || "").join(" ").toLocaleLowerCase();
    if (!header || !(headerText.includes(wanted) || headerTitle.includes(wanted))) {
      return "The selected chat could not be verified as '" + receiver + "'. No message was sent.";
    }

    const composer = [...document.querySelectorAll('#main footer [contenteditable="true"][role="textbox"], #main footer [contenteditable="true"]')].find(visible);
    if (!composer) return "The verified chat is open, but its message box was not found. No message was sent.";
    setText(composer, message);
    await sleep(250);
    const send = [...document.querySelectorAll('#main button[aria-label="Send"], #main [data-testid="send"]')].find(visible);
    if (send) send.click();
    else composer.dispatchEvent(new KeyboardEvent("keydown", {key:"Enter",code:"Enter",keyCode:13,which:13,bubbles:true}));
    await sleep(1000);

    const sent = [...document.querySelectorAll('#main .message-out')].some(el => (el.innerText || "").includes(message));
    return sent ? "WhatsApp message sent and visible in the verified chat with " + receiver + "." :
      "The send action was attempted, but the message could not be confirmed in the chat. Please check WhatsApp.";
  }

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request?.type !== "NOVA_WHATSAPP_SEND") return;
    run(String(request.receiver || ""), String(request.message || ""))
      .then(result => sendResponse({done:true, result}))
      .catch(error => sendResponse({done:true, result:"WhatsApp page error: " + String(error) + ". No message was confirmed."}));
    return true;
  });
})();
