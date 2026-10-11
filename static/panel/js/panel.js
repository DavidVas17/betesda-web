(() => {
  "use strict";

  const body = document.body;
  const navigation = document.getElementById("panel-navigation");
  const toggle = document.querySelector("[data-menu-toggle]");
  const overlay = document.querySelector("[data-menu-close]");
  const mobile = window.matchMedia("(max-width: 1080px)");
  body.classList.add("is-enhanced");

  const closeActionMenus = (except) => {
    document.querySelectorAll(".p-actions-menu[open]").forEach((menu) => {
      if (menu !== except) menu.open = false;
    });
  };

  const setNavigation = (open, returnFocus = true) => {
    if (!navigation || !toggle || !overlay) return;
    const isOpen = mobile.matches && open;
    body.classList.toggle("p-menu-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Cerrar menú" : "Abrir menú");
    overlay.hidden = !isOpen;
    navigation.inert = mobile.matches && !isOpen;
    if (navigation.inert) navigation.setAttribute("aria-hidden", "true");
    else navigation.removeAttribute("aria-hidden");
    if (isOpen) {
      closeActionMenus();
      navigation.querySelector("a, button")?.focus();
    } else if (returnFocus && mobile.matches) toggle.focus();
  };

  if (navigation && toggle && overlay) {
    setNavigation(false, false);
    toggle.addEventListener("click", () => setNavigation(!body.classList.contains("p-menu-open")));
    overlay.addEventListener("click", () => setNavigation(false));
    mobile.addEventListener("change", () => setNavigation(false, false));
    document.addEventListener("keydown", (event) => {
      if (!body.classList.contains("p-menu-open")) return;
      if (event.key === "Escape") { event.preventDefault(); setNavigation(false); }
      if (event.key === "Tab") {
        const focusable = [...navigation.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled])')];
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    });
  }

  document.querySelectorAll("[data-dismiss-notice]").forEach((button) => {
    button.addEventListener("click", () => {
      button.closest(".p-notice")?.remove();
      document.getElementById("contenido")?.focus();
    });
  });

  document.querySelectorAll(".p-actions-menu").forEach((menu) => {
    const summary = menu.querySelector("summary");
    const popover = menu.querySelector(".p-actions-popover");
    if (!summary || !popover) return;
    menu.addEventListener("toggle", () => {
      summary.setAttribute("aria-expanded", String(menu.open));
      if (!menu.open) return;
      closeActionMenus(menu);
      const position = summary.getBoundingClientRect();
      const popoverWidth = popover.offsetWidth;
      const popoverHeight = popover.offsetHeight;
      const left = Math.max(8, Math.min(position.right - popoverWidth, window.innerWidth - popoverWidth - 8));
      let top = position.bottom + 5;
      if (top + popoverHeight > window.innerHeight - 8 && position.top > popoverHeight + 8) top = position.top - popoverHeight - 5;
      popover.style.left = `${left}px`;
      popover.style.top = `${Math.max(8, top)}px`;
      popover.style.maxHeight = `${Math.max(100, window.innerHeight - Math.max(8, top) - 8)}px`;
      popover.style.overflowY = "auto";
    });
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".p-actions-menu")) closeActionMenus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openMenu = document.querySelector(".p-actions-menu[open]");
    if (openMenu) { closeActionMenus(); openMenu.querySelector("summary")?.focus(); }
  });
  window.addEventListener("resize", () => closeActionMenus());
  window.addEventListener("scroll", () => closeActionMenus(), { passive: true });

  const previewUrls = new Map();
  const releasePreview = (input) => {
    (previewUrls.get(input) || []).forEach((url) => URL.revokeObjectURL(url));
    previewUrls.delete(input);
  };
  document.querySelectorAll("input[type='file']").forEach((input) => {
    const preview = [...document.querySelectorAll("[data-upload-preview-for]")].find((element) => element.dataset.uploadPreviewFor === input.id);
    if (!preview) return;
    input.addEventListener("change", () => {
      releasePreview(input);
      preview.replaceChildren();
      const files = [...(input.files || [])];
      preview.hidden = files.length === 0;
      const urls = [];
      const maxPreview = 12;
      files.slice(0, maxPreview).forEach((file) => {
        const figure = document.createElement("figure");
        if (file.type.startsWith("image/")) {
          const url = URL.createObjectURL(file);
          urls.push(url);
          const image = document.createElement("img");
          image.src = url;
          image.alt = "Vista previa de la imagen seleccionada";
          figure.append(image);
        }
        const caption = document.createElement("figcaption");
        caption.textContent = file.name;
        figure.append(caption);
        preview.append(figure);
      });
      if (files.length > maxPreview) {
        const summary = document.createElement("p");
        summary.className = "p-preview-summary";
        summary.textContent = `${files.length} archivos seleccionados. Se muestran los primeros ${maxPreview}.`;
        preview.append(summary);
      }
      previewUrls.set(input, urls);
    });
    input.form?.addEventListener("reset", () => {
      releasePreview(input);
      preview.replaceChildren();
      preview.hidden = true;
    });
  });
  window.addEventListener("pagehide", () => {
    [...previewUrls.keys()].forEach(releasePreview);
  });
})();
