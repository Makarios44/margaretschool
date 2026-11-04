// Ao escolher a categoria de um evento novo, sugere se "não há aula" (feriados, recesso etc.).
document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("id_categoria");
  const caixa = document.getElementById("id_sem_aula");
  const dados = document.getElementById("categoria-padroes");
  if (!sel || !caixa || !dados || sel.dataset.novo !== "1") return;
  const padroes = JSON.parse(dados.textContent);
  const aplicar = () => { if (sel.value in padroes) caixa.checked = padroes[sel.value]; };
  sel.addEventListener("change", aplicar);
  aplicar();
});
