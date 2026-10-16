/*
 * Formularios amigables, compartidos por el sitio público y el panel.
 *
 * Se activa en <form data-enhanced-form>. Todo es mejora progresiva: sin JavaScript el
 * formulario funciona igual y el servidor sigue validando cada dato.
 *
 * - Mensajes de validación claros en español, junto al campo, al salir de él.
 * - Resumen de errores con enlaces a cada campo cuando se intenta enviar.
 * - Contador de caracteres en campos con límite (maxlength).
 * - Botón para mostrar u ocultar contraseñas.
 * - Botón de envío con estado "Guardando…" que evita envíos dobles.
 * - Aviso al salir con cambios sin guardar (data-dirty-guard).
 * - Fecha de fin que no puede ser anterior a la de inicio (data-starts / data-ends).
 * - Zona de arrastrar y soltar para archivos.
 */
(() => {
  "use strict";

  const FIELD_SELECTOR = "input:not([type=hidden]):not([type=submit]):not([type=button]):not([tabindex='-1']), select, textarea";

  const labelText = (field) => {
    const label = field.id && document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
    if (!label) return "Este campo";
    const text = [...label.childNodes]
      .filter((node) => node.nodeType === Node.TEXT_NODE || (node.nodeType === Node.ELEMENT_NODE && !node.matches("[aria-hidden], .p-field-optional, .contact-optional, .contact-required, .p-required, input")))
      .map((node) => node.textContent)
      .join(" ")
      .replace(/\s+/g, " ")
      .replace(/[*:]/g, "")
      .trim()
      .replace(/[.。]$/, "");
    return text || "Este campo";
  };

  const messageFor = (field) => {
    const v = field.validity;
    if (v.valid) return "";
    if (v.valueMissing) {
      if (field.type === "checkbox") return "Marca esta casilla para continuar.";
      if (field.type === "file") return "Selecciona un archivo.";
      if (field.tagName === "SELECT") return "Elige una opción.";
      return "Este dato es necesario.";
    }
    if (v.typeMismatch) {
      if (field.type === "email") return "Revisa el correo; debe verse como nombre@correo.com.";
      if (field.type === "url") return "Escribe el enlace completo, empezando con https://.";
      return "Revisa el formato de este dato.";
    }
    if (v.tooLong) return `Usa como máximo ${field.maxLength} caracteres.`;
    if (v.tooShort) return `Escribe al menos ${field.minLength} caracteres.`;
    if (v.rangeUnderflow) return field.dataset.minMessage || `El valor mínimo es ${field.min}.`;
    if (v.rangeOverflow) return `El valor máximo es ${field.max}.`;
    if (v.patternMismatch) return field.title || "Revisa el formato de este dato.";
    if (v.badInput) return "Revisa este dato; parece incompleto.";
    if (v.customError) return field.validationMessage;
    return "Revisa este dato.";
  };

  const errorBox = (field) => {
    let box = document.getElementById(`${field.id}_error`);
    if (!box) {
      box = document.createElement("div");
      box.id = `${field.id}_error`;
      box.className = "fk-error";
      const container = field.closest(".p-field, .contact-field") || field.parentElement;
      const anchor = container.querySelector(".p-field-help, .contact-help, .fk-counter-row");
      if (anchor && anchor.parentElement === container) anchor.after(box);
      else container.append(box);
    }
    const ids = new Set((field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    ids.add(box.id);
    field.setAttribute("aria-describedby", [...ids].join(" "));
    return box;
  };

  const showError = (field, message) => {
    const box = errorBox(field);
    box.replaceChildren();
    box.hidden = !message;
    field.closest(".p-field, .contact-field")?.classList.toggle("fk-invalid", Boolean(message));
    if (message) {
      const item = document.createElement("p");
      item.textContent = message;
      box.append(item);
      field.setAttribute("aria-invalid", "true");
    } else {
      field.removeAttribute("aria-invalid");
    }
  };

  const check = (field) => {
    const message = messageFor(field);
    showError(field, message);
    return !message;
  };

  const radioGroups = (fields) => {
    // Un grupo de radios o de casillas múltiples se valida una sola vez.
    const seen = new Set();
    return fields.filter((field) => {
      if (field.type !== "radio") return true;
      if (seen.has(field.name)) return false;
      seen.add(field.name);
      return true;
    });
  };

  const renderSummary = (form, invalid) => {
    form.querySelector(".fk-summary[data-client]")?.remove();
    if (!invalid.length) return;
    const summary = document.createElement("div");
    summary.className = "fk-summary";
    summary.dataset.client = "";
    summary.tabIndex = -1;
    summary.setAttribute("role", "alert");
    const title = document.createElement("strong");
    title.textContent = invalid.length === 1 ? "Falta revisar un dato:" : `Faltan revisar ${invalid.length} datos:`;
    const list = document.createElement("ul");
    invalid.forEach((field) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = `#${field.id}`;
      link.textContent = `${labelText(field)}: ${messageFor(field)}`;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        field.focus();
        field.scrollIntoView({ block: "center", behavior: "smooth" });
      });
      item.append(link);
      list.append(item);
    });
    summary.append(title, list);
    const server = form.querySelector(".fk-summary:not([data-client])");
    if (server) server.hidden = true;
    form.prepend(summary);
    summary.focus();
    summary.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  const addCounter = (field) => {
    const max = field.maxLength;
    if (!max || max < 0 || max > 100000 || field.type === "password" || field.readOnly || field.disabled) return;
    const row = document.createElement("div");
    row.className = "fk-counter-row";
    const counter = document.createElement("span");
    counter.className = "fk-counter";
    counter.setAttribute("aria-hidden", "true");
    const live = document.createElement("span");
    live.className = "fk-sr-only";
    live.setAttribute("aria-live", "polite");
    row.append(counter, live);
    let announced = false;
    // En textos largos el contador siempre ayuda; en campos cortos solo aparece cerca del límite.
    const alwaysVisible = field.tagName === "TEXTAREA";
    const update = () => {
      const used = field.value.length;
      const left = max - used;
      row.hidden = !alwaysVisible && used < max * 0.7;
      counter.textContent = `${used.toLocaleString("es-GT")} / ${max.toLocaleString("es-GT")}`;
      counter.classList.toggle("is-near", left <= Math.max(10, max * 0.1));
      counter.classList.toggle("is-full", left <= 0);
      if (left <= Math.max(10, max * 0.1) && !announced) {
        live.textContent = `Quedan ${left} caracteres.`;
        announced = true;
      } else if (left > Math.max(10, max * 0.1)) {
        announced = false;
        live.textContent = "";
      }
    };
    field.after(row);
    field.addEventListener("input", update);
    update();
  };

  const addPasswordToggle = (field) => {
    if (field.dataset.noToggle !== undefined) return;
    const wrap = document.createElement("div");
    wrap.className = "fk-password";
    field.before(wrap);
    wrap.append(field);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "fk-password-toggle";
    button.setAttribute("aria-controls", field.id);
    const render = () => {
      const visible = field.type === "text";
      button.textContent = visible ? "Ocultar" : "Mostrar";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute("aria-label", visible ? "Ocultar contraseña" : "Mostrar contraseña");
    };
    button.addEventListener("click", () => {
      field.type = field.type === "password" ? "text" : "password";
      render();
      field.focus();
    });
    wrap.append(button);
    render();
  };

  const addDropZone = (field) => {
    const zone = field.closest(".p-field, .contact-field");
    if (!zone) return;
    zone.classList.add("fk-drop");
    ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add("is-dragging");
    }));
    ["dragleave", "dragend", "drop"].forEach((type) => zone.addEventListener(type, () => zone.classList.remove("is-dragging")));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      if (!event.dataTransfer?.files?.length) return;
      const transfer = new DataTransfer();
      [...event.dataTransfer.files].slice(0, field.multiple ? undefined : 1).forEach((file) => transfer.items.add(file));
      field.files = transfer.files;
      field.dispatchEvent(new Event("change", { bubbles: true }));
    });
  };

  const linkDates = (form) => {
    const starts = form.querySelector("[data-starts]");
    const ends = form.querySelector("[data-ends]");
    if (!starts || !ends) return;
    const sync = () => {
      ends.min = starts.value || "";
      ends.dataset.minMessage = "La finalización no puede ser antes del inicio.";
      if (ends.value && starts.value && ends.value < starts.value) check(ends);
    };
    starts.addEventListener("change", sync);
    sync();
  };

  const setBusy = (form, busy) => {
    form.querySelectorAll("button[type=submit], button:not([type])").forEach((button) => {
      if (busy) {
        button.dataset.idleHtml = button.innerHTML;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        const label = button.dataset.loadingLabel || form.dataset.loadingLabel || "Guardando…";
        button.innerHTML = `<span class="fk-spinner" aria-hidden="true"></span><span>${label}</span>`;
      } else if (button.dataset.idleHtml) {
        button.innerHTML = button.dataset.idleHtml;
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    });
  };

  const enhance = (form) => {
    form.noValidate = true;
    const fields = () => [...form.querySelectorAll(FIELD_SELECTOR)].filter((field) => !field.disabled && (field.offsetParent !== null || field.type === "file"));
    let dirty = false;
    let submitting = false;
    // Si la persona va directo al botón de enviar, no mostramos el aviso al salir del campo:
    // ese aviso movería el botón y el clic se perdería. La validación ocurre igual al enviar.
    let headingToSubmit = false;
    form.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button[type=submit], button:not([type])")) {
        headingToSubmit = true;
        setTimeout(() => { headingToSubmit = false; }, 600);
      }
    });

    form.querySelectorAll(FIELD_SELECTOR).forEach((field) => {
      if (!field.id) return;
      if (field.type === "password") addPasswordToggle(field);
      if (field.type === "file") addDropZone(field);
      const countable = field.tagName === "TEXTAREA" || (field.tagName === "INPUT" && ["text", "email", "url", "tel", "search"].includes(field.type));
      if (countable && !form.hasAttribute("data-no-counter")) addCounter(field);
      // Valida al salir del campo y, si ya mostró un error, mientras se corrige.
      field.addEventListener("blur", (event) => {
        const toSubmit = headingToSubmit || event.relatedTarget?.matches?.("button[type=submit], button:not([type])");
        if (!toSubmit && (field.value || field.dataset.touched)) check(field);
        field.dataset.touched = "1";
      });
      field.addEventListener("input", () => {
        dirty = true;
        if (field.getAttribute("aria-invalid") === "true") check(field);
      });
      field.addEventListener("change", () => {
        dirty = true;
        if (field.type === "checkbox" || field.type === "radio" || field.tagName === "SELECT") check(field);
      });
    });
    linkDates(form);

    form.addEventListener("submit", (event) => {
      if (submitting) { event.preventDefault(); return; }
      const invalid = radioGroups(fields()).filter((field) => !check(field));
      if (invalid.length) {
        event.preventDefault();
        renderSummary(form, invalid);
        return;
      }
      submitting = true;
      setBusy(form, true);
    });

    if (form.hasAttribute("data-dirty-guard")) {
      window.addEventListener("beforeunload", (event) => {
        if (!dirty || submitting) return;
        event.preventDefault();
        event.returnValue = "";
      });
    }

    // Si el navegador restaura la página desde la caché al volver atrás, el botón vuelve a su estado.
    window.addEventListener("pageshow", () => { submitting = false; setBusy(form, false); });

    // Errores que devolvió el servidor: lleva la atención al resumen.
    const serverSummary = form.querySelector(".fk-summary:not([data-client])");
    if (serverSummary) {
      serverSummary.tabIndex = -1;
      serverSummary.focus();
    }
  };

  document.querySelectorAll("form[data-enhanced-form]").forEach(enhance);
})();
