window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-rfq]").forEach((form) => {
    const whatsapp = form.querySelector("[data-rfq-whatsapp]");
    const mail = form.querySelector("[data-rfq-mail]");
    const field = (name) => form.querySelector(`[data-rfq-${name}]`);
    if (!whatsapp || !mail || !field("product") || !field("qty") || !field("place")) return;

    const phone = (form.dataset.rfqPhone || "").replace(/\D/g, "");
    const email = form.dataset.rfqEmail || "";
    const defaults = { whatsapp: whatsapp.href, mail: mail.href };

    const update = () => {
      const product = field("product").value.trim();
      const quantity = field("qty").value.trim();
      const place = field("place").value.trim();
      if (!product && !quantity && !place) {
        whatsapp.href = defaults.whatsapp;
        mail.href = defaults.mail;
        return;
      }
      const lines = [
        "Hello NAWA Global, I would like a quote for:",
        "",
        `Product / part number: ${product || "-"}`,
        `Quantity: ${quantity || "-"}`,
        `Delivery location: ${place || "-"}`,
      ];
      const body = lines.join("\n");
      whatsapp.href = `https://wa.me/${phone}?text=${encodeURIComponent(body)}`;
      mail.href = `mailto:${email}?subject=${encodeURIComponent(
        `Quote request${product ? ` - ${product}` : ""}`,
      )}&body=${encodeURIComponent(`${body}\n`)}`;
    };

    form.addEventListener("input", update);
    form.addEventListener("submit", (event) => event.preventDefault());
  });
});
