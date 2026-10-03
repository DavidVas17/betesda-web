/* Subida masiva de fotografías: arrastrar y soltar, vista previa y resumen. */
(function () {
  "use strict";

  var MAX_FILES = 30;
  var MAX_MB = 8;

  function init() {
    var zone = document.getElementById("bo-dropzone");
    var input = document.getElementById("id_images");
    var previews = document.getElementById("bo-previews");
    var summary = document.getElementById("bo-upload-summary");
    if (!zone || !input || !previews || !summary) {
      return;
    }

    var urls = [];

    function render() {
      urls.forEach(URL.revokeObjectURL);
      urls = [];
      previews.textContent = "";
      var files = Array.prototype.slice.call(input.files || []);
      var totalBytes = 0;
      var tooBig = 0;

      files.forEach(function (file) {
        totalBytes += file.size;
        if (file.size > MAX_MB * 1024 * 1024) {
          tooBig += 1;
        }
        if (file.type.indexOf("image/") !== 0) {
          return;
        }
        var url = URL.createObjectURL(file);
        urls.push(url);
        var figure = document.createElement("figure");
        var img = document.createElement("img");
        img.src = url;
        img.alt = "";
        var caption = document.createElement("figcaption");
        caption.textContent = file.name;
        figure.appendChild(img);
        figure.appendChild(caption);
        previews.appendChild(figure);
      });

      if (!files.length) {
        summary.textContent = "";
        return;
      }
      var text = files.length + " archivo(s) · " + (totalBytes / 1048576).toFixed(1) + " MB";
      if (files.length > MAX_FILES) {
        text += " — máximo " + MAX_FILES + " por carga";
      }
      if (tooBig) {
        text += " — " + tooBig + " superan los " + MAX_MB + " MB";
      }
      summary.textContent = text;
    }

    input.addEventListener("change", render);

    ["dragenter", "dragover"].forEach(function (name) {
      zone.addEventListener(name, function (event) {
        event.preventDefault();
        zone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (name) {
      zone.addEventListener(name, function (event) {
        event.preventDefault();
        zone.classList.remove("is-dragover");
      });
    });
    zone.addEventListener("drop", function (event) {
      if (event.dataTransfer && event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        render();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
