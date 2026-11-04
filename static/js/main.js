// Mostrar/ocultar senha na tela de login
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("toggle-password");
  const input = document.getElementById("id_password");
  if (!btn || !input) return;

  btn.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-pressed", String(show));
    btn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
    btn.firstElementChild.className = show ? "bi bi-eye-slash" : "bi bi-eye";
  });
});

// Adicionar linhas nos formulários de responsáveis e contatos
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-add-row]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prefix = btn.dataset.addRow;
      const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
      const tpl = document.getElementById(`${prefix}-empty`);
      const rows = document.getElementById(`${prefix}-rows`);
      if (!total || !tpl || !rows) return;
      rows.insertAdjacentHTML("beforeend", tpl.innerHTML.replaceAll("__prefix__", total.value));
      total.value = Number(total.value) + 1;
      const novo = rows.lastElementChild.querySelector("input:not([type=hidden])");
      if (novo) novo.focus();
    });
  });
});
