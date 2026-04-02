window.addEventListener("DOMContentLoaded", () => {
  const imageData = document.getElementById("product-images-data");
  const images = imageData ? JSON.parse(imageData.dataset.images || "[]") : [];
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
    lightboxCounter.textContent = `${index + 1} / ${images.length}`;
    lightboxThumbs.innerHTML = images
      .map(
        (src, thumbIndex) =>
          `<img src="${src}" class="lightbox-thumb${
            thumbIndex === index ? " active" : ""
          }" data-lightbox-index="${thumbIndex}">`,
      )
      .join("");
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
      if (mainImage) mainImage.src = images[index];
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
      index = (index + 1) % images.length;
      render();
    }
    if (event.key === "ArrowLeft") {
      index = (index - 1 + images.length) % images.length;
      render();
    }
    if (event.key === "Escape") close();
  });
});
