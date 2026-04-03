window.addEventListener("DOMContentLoaded", () => {
  const imageData = document.getElementById("product-images-data");
  let images = [];
  if (imageData?.dataset.images) {
    try {
      images = JSON.parse(imageData.dataset.images);
    } catch {
      images = [];
    }
  }
  const lightbox = document.getElementById("lightbox");
  const mainImage = document.getElementById("main-gallery-img");
  const lightboxImage = document.getElementById("lb-img");
  const lightboxCounter = document.getElementById("lb-ctr");
  const lightboxThumbs = document.getElementById("lb-thumbs");
  const openTrigger = document.querySelector("[data-open-lightbox]");
  const thumbs = Array.from(document.querySelectorAll("[data-thumb-index]"));
  let index = 0;

  const render = () => {
    if (!images.length) return;
    lightboxImage.src = images[index];
    lightboxImage.alt = `Product image ${index + 1}`;
    lightboxCounter.textContent = `${index + 1} / ${images.length}`;
    lightboxThumbs.replaceChildren(
      ...images.map((src, thumbIndex) => {
        const thumb = document.createElement("img");
        thumb.src = src;
        thumb.alt = `Preview ${thumbIndex + 1}`;
        thumb.className = `lightbox-thumb${thumbIndex === index ? " active" : ""}`;
        thumb.dataset.lightboxIndex = String(thumbIndex);
        return thumb;
      }),
    );
  };

  const open = (nextIndex) => {
    if (!images.length || !lightbox) return;
    index = nextIndex;
    render();
    lightbox.classList.add("open");
    document.body.style.overflow = "hidden";
  };

  const close = () => {
    if (!lightbox) return;
    lightbox.classList.remove("open");
    document.body.style.overflow = "";
  };

  openTrigger?.addEventListener("click", () => open(index));
  document.querySelector("[data-lightbox-close]")?.addEventListener("click", close);
  document.querySelectorAll("[data-lightbox-step]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!images.length) return;
      index = (index + Number(button.getAttribute("data-lightbox-step")) + images.length) % images.length;
      render();
    });
  });

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const thumbIndex = Number(thumb.getAttribute("data-thumb-index"));
      index = thumbIndex;
      thumbs.forEach((item) => item.classList.remove("active"));
      thumb.classList.add("active");
      if (mainImage) {
        mainImage.src = images[index];
        mainImage.alt = `Product image ${thumbIndex + 1}`;
      }
    });
  });

  lightbox?.addEventListener("click", (event) => {
    if (event.target === lightbox) close();
    const target = event.target;
    if (target instanceof HTMLElement && target.dataset.lightboxIndex) {
      index = Number(target.dataset.lightboxIndex);
      render();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!lightbox?.classList.contains("open")) return;
    if (event.key === "ArrowRight") {
      if (!images.length) return;
      index = (index + 1) % images.length;
      render();
    }
    if (event.key === "ArrowLeft") {
      if (!images.length) return;
      index = (index - 1 + images.length) % images.length;
      render();
    }
    if (event.key === "Escape") close();
  });
});
