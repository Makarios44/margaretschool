// Recebimento: sugere multa/juros conforme a data e mostra o total.
(() => {
  const form = document.getElementById("form-pagamento");
  if (!form) return;
  const valor = parseFloat(form.dataset.valor);
  const pctMulta = parseFloat(form.dataset.multa);
  const pctJuros = parseFloat(form.dataset.juros);
  const campo = (n) => document.getElementById(`id_${n}`);
  const data = campo("data_pagamento"), desc = campo("desconto");
  const multa = campo("multa"), juros = campo("juros");
  const total = document.getElementById("total-pagar");
  const num = (el) => parseFloat(el.value) || 0;
  const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const base = () => Math.max(valor - num(desc), 0);

  function atualizarTotal() {
    total.textContent = brl(base() + num(multa) + num(juros));
  }

  function sugerir() {
    const dias = Math.round((Date.parse(data.value) - Date.parse(form.dataset.vencimento)) / 86400000);
    const atraso = Number.isFinite(dias) && dias > 0;
    if (!multa.dataset.manual) multa.value = (atraso ? (base() * pctMulta) / 100 : 0).toFixed(2);
    if (!juros.dataset.manual) juros.value = (atraso ? (base() * pctJuros) / 100 / 30 * dias : 0).toFixed(2);
    atualizarTotal();
  }

  [data, desc].forEach((el) => el.addEventListener("input", sugerir));
  [multa, juros].forEach((el) =>
    el.addEventListener("input", () => { el.dataset.manual = "1"; atualizarTotal(); })
  );
  atualizarTotal();
})();
