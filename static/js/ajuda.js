// Tutorial: um passo por vez (com JavaScript) e tamanho de letra ajustável.
// Sem JavaScript a página mostra todos os passos em sequência e continua funcionando.
(function () {
  const raiz = document.getElementById("ajuda");
  if (!raiz) return;
  const passos = Array.from(raiz.querySelectorAll(".passo"));
  const voltar = document.getElementById("ajuda-voltar");
  const proximo = document.getElementById("ajuda-proximo");
  const fim = document.getElementById("ajuda-fim");
  const barra = document.getElementById("ajuda-barra");
  const numero = document.getElementById("ajuda-n");
  const progresso = raiz.querySelector(".ajuda-progresso");
  let atual = 0;

  // ----- tamanho da letra (lembrado neste aparelho, se o navegador deixar) -----
  const tamanhos = [1, 1.15, 1.3, 1.5];
  let nivel = 1;
  try { const salvo = parseInt(localStorage.getItem("ajuda-letra"), 10); if (salvo >= 0 && salvo < tamanhos.length) nivel = salvo; } catch (e) {}
  function aplicarLetra() {
    raiz.style.setProperty("--ajuda-escala", tamanhos[nivel]);
    try { localStorage.setItem("ajuda-letra", String(nivel)); } catch (e) {}
  }
  raiz.querySelectorAll("[data-letra]").forEach((b) => b.addEventListener("click", () => {
    nivel = Math.min(tamanhos.length - 1, Math.max(0, nivel + parseInt(b.dataset.letra, 10)));
    aplicarLetra();
  }));
  aplicarLetra();

  // ----- um passo por vez -----
  raiz.classList.add("com-js");
  progresso.hidden = false; voltar.hidden = false; proximo.hidden = false;
  function mostrar(i, foco) {
    atual = Math.min(passos.length - 1, Math.max(0, i));
    passos.forEach((p, k) => { p.hidden = k !== atual; });
    numero.textContent = atual + 1;
    barra.style.width = ((atual + 1) / passos.length * 100) + "%";
    progresso.querySelector("[role=progressbar]").setAttribute("aria-valuenow", atual + 1);
    voltar.disabled = atual === 0;
    const ultimo = atual === passos.length - 1;
    proximo.hidden = ultimo;
    fim.hidden = !ultimo;
    if (foco) {
      const titulo = passos[atual].querySelector(".passo-titulo");
      titulo.setAttribute("tabindex", "-1"); titulo.focus({ preventScroll: true });
      raiz.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    }
  }
  voltar.addEventListener("click", () => mostrar(atual - 1, true));
  proximo.addEventListener("click", () => mostrar(atual + 1, true));
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    if (e.key === "ArrowRight") mostrar(atual + 1, true);
    if (e.key === "ArrowLeft") mostrar(atual - 1, true);
  });
  window.addEventListener("beforeprint", () => passos.forEach((p) => { p.hidden = false; }));
  window.addEventListener("afterprint", () => mostrar(atual, false));
  mostrar(0, false);
})();
