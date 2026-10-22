(() => {
  const STORAGE_KEY = "nawa-quote";
  const MAX_ITEMS = 30;
  const MAX_QTY = 99999;

  const clean = (value, max) => String(value ?? "").replace(/\s+/g, " ").trim().slice(0, max);
  const clampQty = (value) => Math.min(MAX_QTY, Math.max(1, Math.floor(Number(value)) || 1));

  const sanitize = (raw) => {
    if (!raw || typeof raw !== "object") return null;
    const name = clean(raw.name, 120);
    if (!name) return null;
    return { name, spec: clean(raw.spec, 120), qty: clampQty(raw.qty) };
  };

  // The same item and spec merge into one line, so repeated adds raise the quantity.
  const mergeItem = (items, entry) => {
    const item = sanitize(entry);
    if (!item) return items;
    const key = (value) => `${value.name}|${value.spec}`.toLowerCase();
    const existing = items.find((current) => key(current) === key(item));
    if (existing) {
      existing.qty = clampQty(existing.qty + item.qty);
      return items;
    }
    if (items.length < MAX_ITEMS) items.push(item);
    return items;
  };

  const buildMessage = (items, place) => {
    const lines = ["Hello NAWA Global, I would like a quote for:", ""];
    items.forEach((item, index) => {
      lines.push(
        `${index + 1}. ${item.name}${item.spec ? ` (${item.spec})` : ""} - Qty: ${item.qty}`,
      );
    });
    if (place) lines.push("", `Delivery location: ${place}`);
    return lines.join("\n");
  };

  if (typeof window !== "undefined") window.NawaQuote = { sanitize, mergeItem, buildMessage };

  const load = () => {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed)
        ? parsed.map(sanitize).filter(Boolean).slice(0, MAX_ITEMS)
        : [];
    } catch {
      return [];
    }
  };

  window.addEventListener("DOMContentLoaded", () => {
    let items = load();
    let place = "";
    let lastFocus = null;
    let toastTimer;
    const forms = Array.from(document.querySelectorAll("[data-rfq]"));
    const drawer = document.querySelector("[data-quote-drawer]");

    const save = () => {
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
      } catch {
        // Private mode or blocked storage: the list still works for this page view.
      }
    };

    const pending = (form) =>
      sanitize({
        name: form.querySelector("[data-rfq-name]")?.value,
        spec: form.querySelector("[data-rfq-spec]")?.value,
        qty: form.querySelector("[data-rfq-qty]")?.value,
      });

    // Send links include the list plus whatever is typed but not yet added.
    const updateLinks = (form) => {
      const whatsapp = form.querySelector("[data-rfq-whatsapp]");
      const mail = form.querySelector("[data-rfq-mail]");
      if (!whatsapp || !mail) return;
      if (!form.dataset.defaultWhatsapp) {
        form.dataset.defaultWhatsapp = whatsapp.href;
        form.dataset.defaultMail = mail.href;
      }
      const all = items.map((item) => ({ ...item }));
      const typed = pending(form);
      if (typed) mergeItem(all, typed);
      if (!all.length) {
        whatsapp.href = form.dataset.defaultWhatsapp;
        mail.href = form.dataset.defaultMail;
        return;
      }
      const body = buildMessage(all, place);
      const phone = (form.dataset.rfqPhone || "").replace(/\D/g, "");
      whatsapp.href = `https://wa.me/${phone}?text=${encodeURIComponent(body)}`;
      const subject = `Quote request - ${all.length} item${all.length === 1 ? "" : "s"}`;
      mail.href = `mailto:${form.dataset.rfqEmail || ""}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(`${body}\n`)}`;
    };

    const controlButton = (item, index, label, symbol, action) => {
      const control = document.createElement("button");
      control.type = "button";
      control.textContent = symbol;
      control.setAttribute("aria-label", `${label} ${item.name}`);
      control.dataset.rfqAction = action;
      control.dataset.index = String(index);
      return control;
    };

    const renderItems = (form) => {
      const list = form.querySelector("[data-rfq-items]");
      if (!list) return;
      list.replaceChildren(
        ...items.map((item, index) => {
          const row = document.createElement("li");
          row.className = "rfq-item";
          const text = document.createElement("div");
          text.className = "rfq-item-text";
          const name = document.createElement("strong");
          name.textContent = item.name;
          text.append(name);
          if (item.spec) {
            const spec = document.createElement("small");
            spec.textContent = item.spec;
            text.append(spec);
          }
          const qty = document.createElement("div");
          qty.className = "rfq-qty";
          const value = document.createElement("span");
          value.textContent = String(item.qty);
          qty.append(
            controlButton(item, index, "Decrease quantity of", "−", "dec"),
            value,
            controlButton(item, index, "Increase quantity of", "+", "inc"),
          );
          const remove = controlButton(item, index, "Remove", "✕", "remove");
          remove.className = "rfq-remove";
          row.append(text, qty, remove);
          return row;
        }),
      );
    };

    const render = () => {
      const count = items.length;
      const total = items.reduce((sum, item) => sum + item.qty, 0);
      forms.forEach((form) => {
        renderItems(form);
        const label = form.querySelector("[data-rfq-count]");
        if (label) {
          label.textContent = count
            ? `${count} item${count === 1 ? "" : "s"} · qty ${total}`
            : "Empty list";
        }
        const clear = form.querySelector("[data-rfq-clear]");
        if (clear) clear.hidden = !count;
        const placeInput = form.querySelector("[data-rfq-place]");
        if (placeInput && placeInput.value !== place) placeInput.value = place;
        updateLinks(form);
      });
      document.querySelectorAll("[data-quote-count]").forEach((badge) => {
        badge.textContent = String(count);
        badge.hidden = !count;
      });
    };

    const commit = () => {
      save();
      render();
    };

    forms.forEach((form) => {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const name = form.querySelector("[data-rfq-name]");
        const entry = pending(form);
        if (!entry) {
          name?.focus();
          return;
        }
        mergeItem(items, entry);
        ["name", "spec"].forEach((field) => {
          const input = form.querySelector(`[data-rfq-${field}]`);
          if (input) input.value = "";
        });
        const qty = form.querySelector("[data-rfq-qty]");
        if (qty) qty.value = "1";
        commit();
        name?.focus();
      });
      form.addEventListener("input", (event) => {
        if (event.target.matches("[data-rfq-place]")) place = clean(event.target.value, 80);
        forms.forEach(updateLinks);
      });
      form.addEventListener("click", (event) => {
        const control = event.target.closest("[data-rfq-action]");
        if (control) {
          const index = Number(control.dataset.index);
          const item = items[index];
          if (!item) return;
          if (control.dataset.rfqAction === "remove") items.splice(index, 1);
          else item.qty = clampQty(item.qty + (control.dataset.rfqAction === "inc" ? 1 : -1));
          commit();
        } else if (event.target.closest("[data-rfq-clear]")) {
          items = [];
          commit();
        }
      });
    });

    const closeDrawer = () => {
      if (!drawer || drawer.hidden) return;
      drawer.hidden = true;
      document.body.classList.remove("quote-open");
      lastFocus?.focus?.();
    };

    const openQuote = () => {
      const inline = forms.find((form) => !drawer?.contains(form));
      if (inline) {
        inline.scrollIntoView({ behavior: "smooth", block: "center" });
        inline.querySelector("[data-rfq-name]")?.focus({ preventScroll: true });
        return;
      }
      if (!drawer) return;
      lastFocus = document.activeElement;
      drawer.hidden = false;
      document.body.classList.add("quote-open");
      drawer.querySelector("[data-rfq-name]")?.focus();
    };

    const showToast = (message) => {
      let toast = document.querySelector(".quote-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.className = "quote-toast";
        toast.setAttribute("role", "status");
        document.body.append(toast);
      }
      const text = document.createElement("span");
      text.textContent = message;
      const view = document.createElement("button");
      view.type = "button";
      view.textContent = "View list";
      view.addEventListener("click", () => {
        toast.classList.remove("show");
        openQuote();
      });
      toast.replaceChildren(text, view);
      toast.classList.add("show");
      window.clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => toast.classList.remove("show"), 4000);
    };

    document.querySelectorAll("[data-quote-add]").forEach((button) => {
      button.hidden = false;
      button.addEventListener("click", () => {
        mergeItem(items, { name: button.dataset.name, qty: 1 });
        commit();
        showToast(`Added “${clean(button.dataset.name, 60)}” to your quote list`);
      });
    });
    document.querySelectorAll("[data-quote-open]").forEach((button) => button.addEventListener("click", openQuote));
    document.querySelectorAll("[data-quote-close]").forEach((button) => button.addEventListener("click", closeDrawer));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeDrawer();
    });
    window.addEventListener("storage", (event) => {
      if (event.key !== STORAGE_KEY) return;
      items = load();
      render();
    });

    render();
  });
})();
