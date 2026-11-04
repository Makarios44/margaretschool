// Chamada diária: contadores ao vivo e "todos presentes". A tela funciona sem JavaScript;
// aqui só entram o conforto e o resumo na barra de baixo.
(function () {
  const form = document.getElementById("form-chamada");
  if (!form) return;
  const itens = Array.from(form.querySelectorAll(".aluno-chamada"));

  function atualizar() {
    const total = { P: 0, F: 0, J: 0 };
    itens.forEach((li) => {
      const marcado = li.querySelector(".seg-input:checked");
      const st = marcado ? marcado.value : "";
      li.dataset.status = st;
      if (st in total) total[st] += 1;
    });
    document.getElementById("c-p").textContent = total.P;
    document.getElementById("c-f").textContent = total.F;
    document.getElementById("c-j").textContent = total.J;
  }

  form.addEventListener("change", (e) => {
    if (!e.target.classList.contains("seg-input")) return;
    atualizar();
    if (e.target.value === "J" || e.target.value === "F") {
      const campo = e.target.closest(".aluno-chamada").querySelector(".just input");
      if (campo && e.target.value === "J" && !campo.value) campo.focus({ preventScroll: true });
    }
  });

  form.querySelector("[data-todos]").addEventListener("click", () => {
    const algumaFalta = itens.some((li) => li.dataset.status === "F" || li.dataset.status === "J");
    if (algumaFalta && !confirm("Isso vai marcar todos como presentes e apagar as faltas marcadas nesta tela. Continuar?")) return;
    itens.forEach((li) => {
      li.querySelector('.seg-input[value="P"]').checked = true;
      li.querySelector(".just input").value = "";
    });
    atualizar();
  });

  atualizar();
})();
