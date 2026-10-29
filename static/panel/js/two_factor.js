/* Verificación en dos pasos: dibuja el QR localmente (el secreto nunca sale del sitio) y
   ofrece copiar la clave o los códigos de respaldo. */
(function () {
  "use strict";

  var qrBox = document.querySelector("[data-otpauth]");
  if (qrBox && typeof window.qrcode === "function") {
    var qr = window.qrcode(0, "M");
    qr.addData(qrBox.getAttribute("data-otpauth"));
    qr.make();
    var img = document.createElement("img");
    img.src = qr.createDataURL(6, 2);
    img.width = img.height = 220;
    img.alt = "Código QR para tu app de verificación";
    qrBox.textContent = "";
    qrBox.appendChild(img);
  }

  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    button.hidden = false;
    button.addEventListener("click", function () {
      var source = document.getElementById(button.getAttribute("data-copy-target"));
      if (!source || !navigator.clipboard) return;
      navigator.clipboard.writeText(source.innerText.trim()).then(function () {
        var original = button.getAttribute("data-label") || button.textContent;
        button.setAttribute("data-label", original);
        button.textContent = "¡Copiado!";
        window.setTimeout(function () { button.textContent = original; }, 2000);
      });
    });
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.hidden = false;
    button.addEventListener("click", function () { window.print(); });
  });
})();
