(function () {
  "use strict";

  var panel = document.getElementById("reader-lookup");
  if (!panel) return;

  var selectionText = panel.querySelector(".reader-lookup-selection");
  var meaningText = panel.querySelector(".reader-lookup-meaning");
  var closeButton = panel.querySelector(".reader-lookup-close");
  var translateButton = panel.querySelector('[data-action="translate"]');
  var speakButton = panel.querySelector('[data-action="speak"]');
  var script = document.currentScript;
  var endpoint = script && script.dataset.translateEndpoint
    ? script.dataset.translateEndpoint.trim()
    : "";
  var activeText = "";
  var selectionTimer = 0;

  function normalize(value) {
    return value
      .toLowerCase()
      .replace(/[.,;:!?"'()[\]{}]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildGlossary() {
    var entries = new Map();
    document.querySelectorAll(".vocab li").forEach(function (item) {
      var termNode = item.querySelector(".term");
      if (!termNode) return;

      var term = termNode.textContent.trim();
      var meaning = item.textContent
        .slice(termNode.textContent.length)
        .replace(/^\s*-\s*/, "")
        .trim();
      if (term && meaning) entries.set(normalize(term), meaning);
    });
    return entries;
  }

  var glossary = buildGlossary();

  function selectedTextFromArticle() {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return "";

    var range = selection.getRangeAt(0);
    var container = range.commonAncestorContainer;
    var element = container.nodeType === Node.ELEMENT_NODE
      ? container
      : container.parentElement;
    if (!element || !element.closest("main.page")) return "";
    if (element.closest("nav, footer, .reader-lookup")) return "";

    var value = selection.toString().replace(/\s+/g, " ").trim();
    if (value.length < 2 || value.length > 180 || !/[A-Za-z]/.test(value)) return "";
    return value;
  }

  function setMeaning(value, isError) {
    meaningText.textContent = value;
    meaningText.style.color = isError ? "#9b2c2c" : "";
  }

  function showPanel(value) {
    activeText = value;
    selectionText.textContent = value;

    var localMeaning = glossary.get(normalize(value));
    if (localMeaning) {
      setMeaning(localMeaning, false);
    } else if (endpoint) {
      setMeaning("Ready to translate.", false);
    } else {
      setMeaning("Open DeepL for the Chinese meaning.", false);
    }

    panel.hidden = false;
  }

  function updateFromSelection() {
    var value = selectedTextFromArticle();
    if (value && value !== activeText) showPanel(value);
  }

  function scheduleSelectionCheck(delay) {
    window.clearTimeout(selectionTimer);
    selectionTimer = window.setTimeout(updateFromSelection, delay || 180);
  }

  function closePanel() {
    panel.hidden = true;
    activeText = "";
  }

  function deepLUrl(value) {
    return "https://www.deepl.com/translator#en/zh/" + encodeURIComponent(value);
  }

  async function translateSelection() {
    if (!activeText) return;

    if (!endpoint) {
      window.open(deepLUrl(activeText), "_blank", "noopener,noreferrer");
      return;
    }

    translateButton.disabled = true;
    translateButton.textContent = "Translating...";
    setMeaning("", false);

    try {
      var response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: activeText, target_lang: "ZH" })
      });
      if (!response.ok) throw new Error("Translation request failed");

      var data = await response.json();
      var translation = data.translation ||
        (data.translations && data.translations[0] && data.translations[0].text);
      if (!translation) throw new Error("No translation returned");
      setMeaning(translation, false);
    } catch (error) {
      setMeaning("Translation is unavailable. Open DeepL instead.", true);
      window.open(deepLUrl(activeText), "_blank", "noopener,noreferrer");
    } finally {
      translateButton.disabled = false;
      translateButton.textContent = "DeepL";
    }
  }

  function speakSelection() {
    if (!activeText || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(activeText);
    utterance.lang = "en-US";
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
  }

  document.addEventListener("selectionchange", function () {
    scheduleSelectionCheck(240);
  });
  document.addEventListener("pointerup", function () {
    scheduleSelectionCheck(80);
  });
  document.addEventListener("touchend", function () {
    scheduleSelectionCheck(360);
  }, { passive: true });
  document.addEventListener("keyup", function (event) {
    if (event.shiftKey || event.key.indexOf("Arrow") === 0) {
      scheduleSelectionCheck(80);
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closePanel();
  });

  closeButton.addEventListener("click", closePanel);
  translateButton.addEventListener("click", translateSelection);
  speakButton.addEventListener("click", speakSelection);

  if (!("speechSynthesis" in window)) speakButton.hidden = true;
})();
