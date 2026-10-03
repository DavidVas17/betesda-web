/* Mejoras de interfaz del panel: contadores de caracteres y vista previa de imágenes. */
(function () {
  "use strict";

  function addCounters() {
    var fields = document.querySelectorAll(
      "#content-main input[type=text][maxlength], #content-main textarea[maxlength]"
    );
    fields.forEach(function (field) {
      var max = parseInt(field.getAttribute("maxlength"), 10);
      if (!max || max > 400 || field.dataset.boCounter || field.closest(".empty-form")) {
        return;
      }
      field.dataset.boCounter = "1";
      var counter = document.createElement("span");
      counter.className = "bo-char-counter";
      counter.setAttribute("aria-live", "polite");
      field.insertAdjacentElement("afterend", counter);

      function update() {
        var used = field.value.length;
        counter.textContent = used + " / " + max + " caracteres";
        counter.classList.toggle("is-near", used >= max * 0.9 && used < max);
        counter.classList.toggle("is-over", used >= max);
      }
      field.addEventListener("input", update);
      update();
    });
  }

  function addImagePreviews() {
    var inputs = document.querySelectorAll(
      "#content-main input[type=file][accept^='image']:not([multiple]), " +
        "#content-main input[type=file][name$='cover_image'], " +
        "#content-main input[type=file][name$='-image']"
    );
    inputs.forEach(function (input) {
      if (input.dataset.boPreview || input.multiple || input.closest(".empty-form")) {
        return;
      }
      input.dataset.boPreview = "1";
      var img = document.createElement("img");
      img.className = "bo-preview";
      img.alt = "Vista previa de la imagen seleccionada";
      img.hidden = true;
      input.insertAdjacentElement("afterend", img);
      input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (!file || file.type.indexOf("image/") !== 0) {
          img.hidden = true;
          return;
        }
        if (img.dataset.url) {
          URL.revokeObjectURL(img.dataset.url);
        }
        img.dataset.url = URL.createObjectURL(file);
        img.src = img.dataset.url;
        img.hidden = false;
      });
    });
  }

  function init() {
    addCounters();
    addImagePreviews();
  }

  // Django dispara este evento cuando se agrega una fila a un inline.
  document.addEventListener("formset:added", init);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
