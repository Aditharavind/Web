(() => {
  const STORAGE_KEY = "nawa-quote";
  const MAX_ITEMS = 30;
  const MAX_QTY = 99999;
  const SUGGEST_URL = "/api/suggest";

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
      lines.push(`${index + 1}. *${item.name}*`);
      if (item.spec) lines.push(`   Spec: ${item.spec}`);
      lines.push(`   Qty: ${item.qty}`, "");
    });
    if (place) lines.push(`Delivery location: ${place}`);
    return lines.join("\n").trimEnd();
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

    const typedItem = (form) => sanitize({ name: form.querySelector("[data-rfq-name]")?.value, qty: 1 });

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
      const typed = typedItem(form);
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

    const element = (tag, className, text) => {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    };

    const control = (item, index, label, symbol, action, className) => {
      const button = element("button", className, symbol);
      button.type = "button";
      button.setAttribute("aria-label", `${label} ${item.name}`);
      button.dataset.rfqAction = action;
      button.dataset.index = String(index);
      return button;
    };

    const renderItem = (item, index) => {
      const row = element("li", "rfq-item");
      const name = element("strong", "rfq-item-name", item.name);
      const remove = control(item, index, "Remove", "✕", "remove", "rfq-remove");

      const spec = element("input", "rfq-spec");
      spec.type = "text";
      spec.maxLength = 120;
      spec.value = item.spec;
      spec.placeholder = "Spec: size, grade, make (optional)";
      spec.setAttribute("aria-label", `Specification for ${item.name}`);
      spec.dataset.rfqSpecEdit = "";
      spec.dataset.index = String(index);

      const qty = element("div", "rfq-qty");
      const amount = element("input", "rfq-qty-input");
      amount.type = "number";
      amount.min = "1";
      amount.max = String(MAX_QTY);
      amount.inputMode = "numeric";
      amount.value = String(item.qty);
      amount.setAttribute("aria-label", `Quantity of ${item.name}`);
      amount.dataset.rfqQtyEdit = "";
      amount.dataset.index = String(index);
      qty.append(
        control(item, index, "Decrease quantity of", "−", "dec"),
        amount,
        control(item, index, "Increase quantity of", "+", "inc"),
      );
      row.append(name, remove, spec, qty);
      return row;
    };

    const render = () => {
      const count = items.length;
      const total = items.reduce((sum, item) => sum + item.qty, 0);
      forms.forEach((form) => {
        form.querySelector("[data-rfq-items]")?.replaceChildren(...items.map(renderItem));
        const empty = form.querySelector("[data-rfq-empty]");
        if (empty) empty.hidden = count > 0;
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

    const addNamed = (form, name) => {
      const entry = sanitize({ name, qty: 1 });
      if (!entry) return false;
      mergeItem(items, entry);
      const input = form.querySelector("[data-rfq-name]");
      if (input) input.value = "";
      commit();
      input?.focus();
      return true;
    };

    // Type-ahead: catalogue matches are only a shortcut; any typed text can still be added.
    const setupSuggestions = (form) => {
      const input = form.querySelector("[data-rfq-name]");
      const list = form.querySelector("[data-rfq-options]");
      if (!input || !list) return { close() {}, handleKey: () => false };
      let matches = [];
      let active = -1;
      let timer;
      let controller;

      const close = () => {
        list.hidden = true;
        list.replaceChildren();
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        matches = [];
        active = -1;
      };

      const highlight = (index) => {
        active = index;
        Array.from(list.children).forEach((option, position) => {
          const selected = position === index;
          option.classList.toggle("active", selected);
          option.setAttribute("aria-selected", String(selected));
          if (selected) input.setAttribute("aria-activedescendant", option.id);
        });
      };

      const show = (typed) => {
        const options = matches.map((match) => ({ name: match.name, detail: match.category }));
        options.push({ name: typed, detail: "Not listed? Add it as typed", custom: true });
        list.replaceChildren(
          ...options.map((option, index) => {
            const row = element("li", `rfq-option${option.custom ? " custom" : ""}`);
            row.id = `${list.id}-${index}`;
            row.setAttribute("role", "option");
            row.dataset.name = option.name;
            const label = element("span", "rfq-option-name", option.custom ? `Add “${option.name}”` : option.name);
            row.append(label);
            if (option.detail) row.append(element("small", "", option.detail));
            return row;
          }),
        );
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
        active = -1;
      };

      const fetchMatches = async (term) => {
        controller?.abort();
        controller = new AbortController();
        try {
          const response = await fetch(`${SUGGEST_URL}?q=${encodeURIComponent(term)}`, {
            signal: controller.signal,
            headers: { Accept: "application/json" },
          });
          if (!response.ok) throw new Error("suggest failed");
          const data = await response.json();
          matches = Array.isArray(data.items) ? data.items.slice(0, 5) : [];
        } catch (error) {
          if (error.name === "AbortError") return;
          matches = [];
        }
        if (clean(input.value, 120) === term) show(term);
      };

      input.addEventListener("input", () => {
        window.clearTimeout(timer);
        const term = clean(input.value, 120);
        if (term.length < 2) {
          close();
          return;
        }
        timer = window.setTimeout(() => fetchMatches(term), 180);
      });

      list.addEventListener("mousedown", (event) => event.preventDefault());
      list.addEventListener("click", (event) => {
        const option = event.target.closest("[role=option]");
        if (!option) return;
        close();
        addNamed(form, option.dataset.name);
      });
      input.addEventListener("blur", () => window.setTimeout(close, 120));

      // Returns true when the key was used by the suggestion list.
      const handleKey = (event) => {
        if (list.hidden) return false;
        const last = list.children.length - 1;
        if (event.key === "ArrowDown") {
          event.preventDefault();
          highlight(active >= last ? 0 : active + 1);
          return true;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          highlight(active <= 0 ? last : active - 1);
          return true;
        }
        if (event.key === "Escape") {
          close();
          event.stopPropagation();
          return true;
        }
        if (event.key === "Enter" && active >= 0) {
          event.preventDefault();
          const name = list.children[active].dataset.name;
          close();
          addNamed(form, name);
          return true;
        }
        return false;
      };

      return { close, handleKey };
    };

    forms.forEach((form) => {
      const suggestions = setupSuggestions(form);
      form.addEventListener("keydown", (event) => {
        if (event.target.matches("[data-rfq-name]")) suggestions.handleKey(event);
      });
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        suggestions.close();
        const input = form.querySelector("[data-rfq-name]");
        if (!addNamed(form, input?.value)) input?.focus();
      });
      form.addEventListener("input", (event) => {
        const target = event.target;
        if (target.matches("[data-rfq-place]")) {
          place = clean(target.value, 80);
        } else if (target.matches("[data-rfq-spec-edit]")) {
          const item = items[Number(target.dataset.index)];
          if (item) {
            item.spec = clean(target.value, 120);
            save();
          }
        } else if (target.matches("[data-rfq-qty-edit]")) {
          const item = items[Number(target.dataset.index)];
          if (item && target.value !== "") {
            item.qty = clampQty(target.value);
            save();
          }
        }
        forms.forEach(updateLinks);
      });
      // After typing a quantity or spec, redraw once so the counts and other lists match.
      form.addEventListener("change", (event) => {
        if (event.target.matches("[data-rfq-spec-edit], [data-rfq-qty-edit]")) render();
      });
      form.addEventListener("click", (event) => {
        const button = event.target.closest("[data-rfq-action]");
        if (button) {
          const index = Number(button.dataset.index);
          const item = items[index];
          if (!item) return;
          if (button.dataset.rfqAction === "remove") items.splice(index, 1);
          else item.qty = clampQty(item.qty + (button.dataset.rfqAction === "inc" ? 1 : -1));
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
        toast = element("div", "quote-toast");
        toast.setAttribute("role", "status");
        document.body.append(toast);
      }
      const view = element("button", "", "View list");
      view.type = "button";
      view.addEventListener("click", () => {
        toast.classList.remove("show");
        openQuote();
      });
      toast.replaceChildren(element("span", "", message), view);
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
