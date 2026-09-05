/* ApplyJin Chrome Extension — Content script
   Runs on all pages. Scans for form fields, extracts JDs, fills forms. */

(() => {
  "use strict";

  /* ---------- field detection ---------- */

  function scanFields() {
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), ' +
      'textarea, ' +
      'select'
    );

    return Array.from(inputs).map((el, i) => {
      const label = findLabel(el);
      const name = el.name || el.id || "";
      const type = el.tagName === "SELECT" ? "select" : el.type || "text";
      const value = el.value || "";
      const selector = buildSelector(el, i);

      return {
        tag: el.tagName.toLowerCase(),
        type,
        name,
        id: el.id,
        label,
        placeholder: el.placeholder || "",
        value,
        selector,
        index: i,
        detectable: isDetectable(name + " " + label + " " + (el.placeholder || "")),
        selected: false,
      };
    });
  }

  function findLabel(el) {
    // Explicit label
    if (el.id) {
      const label = document.querySelector(`label[for="${el.id}"]`);
      if (label) return label.textContent.trim();
    }
    // Wrapped in label
    const parent = el.closest("label");
    if (parent) return parent.textContent.trim();
    // Preceding sibling label
    const prev = el.previousElementSibling;
    if (prev && prev.tagName === "LABEL") return prev.textContent.trim();
    // aria-label
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    // aria-labelledby
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      const lab = document.getElementById(labelledBy);
      if (lab) return lab.textContent.trim();
    }
    // data-testid or similar
    return el.getAttribute("data-testid") || el.getAttribute("data-field") || "";
  }

  function isDetectable(text) {
    const lower = text.toLowerCase();
    const patterns = [
      /first.*name/, /last.*name/, /full.*name/, /email/, /phone/, /tel/,
      /linkedin/, /github/, /portfolio/, /website/, /location/, /city/,
      /address/, /zip/, /postal/, /resume/, /cover.*letter/, /summary/,
      /objective/, /experience/, /education/, /skill/, /salary/, /start.*date/,
      /availability/, /work.*authorization/, /sponsorship/,
    ];
    return patterns.some((p) => p.test(lower));
  }

  function buildSelector(el, index) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `[name="${CSS.escape(el.name)}"]`;
    if (el.getAttribute("data-testid")) return `[data-testid="${el.getAttribute("data-testid")}"]`;
    return `form input:nth-of-type(${index + 1}), form textarea:nth-of-type(${index + 1}), form select:nth-of-type(${index + 1})`;
  }

  /* ---------- JD extraction ---------- */

  function extractJD() {
    // Try common job board patterns
    const selectors = [
      // LinkedIn
      ".description__text",
      ".show-more-less-html__markup",
      // Greenhouse
      ".content",
      "#content",
      // Lever
      ".posting-page .content",
      ".section-wrapper",
      // Workday
      "[data-automation-id='jobPostingDescription']",
      // iCIMS
      ".job-description",
      // Generic
      "article",
      '[role="main"]',
      "main",
    ];

    let jdText = "";
    let title = "";
    let company = "";

    // Title
    const titleEl =
      document.querySelector("h1") ||
      document.querySelector('[data-testid="job-title"]') ||
      document.querySelector(".job-title") ||
      document.querySelector(".posting-headline h2");
    if (titleEl) title = titleEl.textContent.trim();

    // Company
    const companyEl =
      document.querySelector('[data-testid="company-name"]') ||
      document.querySelector(".company-name") ||
      document.querySelector(".org-name") ||
      document.querySelector(".posting-headline h4");
    if (companyEl) company = companyEl.textContent.trim();

    // JD body
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const text = el.innerText || el.textContent || "";
        if (text.length > 100 && text.length > jdText.length) {
          jdText = text;
        }
      }
    }

    // Fallback: collect all paragraphs
    if (!jdText || jdText.length < 100) {
      const paragraphs = document.querySelectorAll("p, li");
      jdText = Array.from(paragraphs)
        .map((p) => p.textContent.trim())
        .filter((t) => t.length > 20)
        .join("\n");
    }

    return {
      title,
      company,
      jd: jdText,
      url: window.location.href,
    };
  }

  /* ---------- form filling ---------- */

  function fillFields(fieldsMap) {
    let filled = 0;
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select'
    );

    inputs.forEach((el) => {
      // Try each selector in the fill map
      for (const [selector, value] of Object.entries(fieldsMap)) {
        try {
          if (selector.startsWith("#") && el.id) {
            if (el.id === selector.slice(1)) {
              setField(el, value);
              filled++;
              return;
            }
          } else if (selector.startsWith("[name=")) {
            const name = selector.match(/name="([^"]+)"/)?.[1];
            if (name && el.name === name) {
              setField(el, value);
              filled++;
              return;
            }
          }
        } catch {}
      }
    });

    return { filled };
  }

  function setField(el, value) {
    if (!value) return;

    // Set value using native input setter to trigger React/Angular change detection
    const nativeSetter = Object.getOwnPropertyDescriptor(
      el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      "value"
    )?.set;

    if (nativeSetter) {
      nativeSetter.call(el, value);
    } else {
      el.value = value;
    }

    // Dispatch events
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  /* ---------- message handler ---------- */

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.action === "scan") {
      const fields = scanFields();
      // Try to get title/company from page
      const titleEl = document.querySelector("h1");
      const title = titleEl ? titleEl.textContent.trim() : "";
      // Simple company heuristic
      const companyEl = document.querySelector(".company-name, .org-name, [data-testid='company-name']");
      const company = companyEl ? companyEl.textContent.trim() : "";

      sendResponse({ fields, title, company });
    }

    if (msg.action === "fill") {
      const result = fillFields(msg.fields);
      sendResponse(result);
    }

    if (msg.action === "extractJD") {
      const data = extractJD();
      sendResponse(data);
    }

    return true; // keep channel open for async
  });
})();
