// Visualização ampliada das fotos do álbum (usa <dialog>: Esc fecha, foco fica preso dentro).
document.addEventListener("DOMContentLoaded", () => {
  const dialogo = document.getElementById("lightbox");
  if (!dialogo) return;
  const imagem = dialogo.querySelector("img");
  const legenda = dialogo.querySelector("[data-lb-legenda]");
  const contador = dialogo.querySelector("[data-lb-contador]");
  const itens = Array.from(document.querySelectorAll("[data-foto-grande]"));
  let atual = 0;

  const mostrar = (indice) => {
    atual = (indice + itens.length) % itens.length;
    const item = itens[atual];
    imagem.src = item.dataset.fotoGrande;
    imagem.alt = item.dataset.legenda || "Foto da atividade";
    legenda.textContent = item.dataset.legenda || "";
    contador.textContent = `${atual + 1} de ${itens.length}`;
  };

  itens.forEach((item, i) => item.addEventListener("click", () => { mostrar(i); dialogo.showModal(); }));
  dialogo.querySelector("[data-lb-ant]").addEventListener("click", () => mostrar(atual - 1));
  dialogo.querySelector("[data-lb-prox]").addEventListener("click", () => mostrar(atual + 1));
  dialogo.querySelector("[data-lb-fechar]").addEventListener("click", () => dialogo.close());
  dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close(); }); // clique fora da foto
  dialogo.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") mostrar(atual - 1);
    if (e.key === "ArrowRight") mostrar(atual + 1);
  });
  dialogo.addEventListener("close", () => { imagem.removeAttribute("src"); });

  let inicioToque = null; // deslizar o dedo troca de foto
  dialogo.addEventListener("touchstart", (e) => { inicioToque = e.touches[0].clientX; }, { passive: true });
  dialogo.addEventListener("touchend", (e) => {
    if (inicioToque === null) return;
    const delta = e.changedTouches[0].clientX - inicioToque;
    if (Math.abs(delta) > 50) mostrar(atual + (delta < 0 ? 1 : -1));
    inicioToque = null;
  });
});
