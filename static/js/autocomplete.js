// Campo de aluno com sugestões enquanto se digita (teclado: ↑ ↓ Enter Esc).
(() => {
  const iniciar = (raiz) => {
    const busca = raiz.querySelector("input[role=combobox]");
    if (!busca) return; // campo somente leitura (edição)
    const oculto = raiz.querySelector("input[type=hidden]");
    const lista = raiz.querySelector(".ac-lista");
    const ajuda = raiz.querySelector("[data-ac-ajuda]");
    const selecionado = raiz.querySelector(".ac-selecionado");
    const areaBusca = raiz.querySelector(".ac-busca");
    const trocar = raiz.querySelector("[data-ac-trocar]");
    const AJUDA_INICIAL = ajuda.textContent;
    let itens = [], ativo = -1, temporizador = null, sequencia = 0;

    const fechar = () => {
      lista.hidden = true;
      busca.setAttribute("aria-expanded", "false");
      busca.removeAttribute("aria-activedescendant");
      ativo = -1;
    };

    const marcar = (indice) => {
      const opcoes = lista.querySelectorAll("[role=option]");
      opcoes.forEach((o, i) => o.classList.toggle("ativo", i === indice));
      ativo = indice;
      if (opcoes[indice]) {
        busca.setAttribute("aria-activedescendant", opcoes[indice].id);
        opcoes[indice].scrollIntoView({ block: "nearest" });
      } else {
        busca.removeAttribute("aria-activedescendant");
      }
    };

    const escolher = (aluno) => {
      oculto.value = aluno.id;
      selecionado.querySelector("[data-ac-nome]").textContent = aluno.nome;
      selecionado.querySelector("[data-ac-detalhe]").textContent = aluno.detalhe;
      selecionado.hidden = false;
      areaBusca.hidden = true;
      fechar();
      oculto.dispatchEvent(new Event("change", { bubbles: true }));
    };

    const desenhar = (dados) => {
      itens = dados.resultados;
      lista.replaceChildren();
      if (!itens.length) {
        const vazio = document.createElement("li");
        vazio.className = "ac-vazio";
        vazio.append("Nenhum aluno encontrado. ");
        const link = document.createElement("a");
        link.href = raiz.dataset.urlNovo;
        link.textContent = "Cadastrar novo aluno";
        vazio.append(link);
        lista.append(vazio);
      } else {
        itens.forEach((aluno, i) => {
          const li = document.createElement("li");
          li.role = "option";
          li.id = `${busca.id}-op-${i}`;
          li.className = "ac-opcao";
          const nome = document.createElement("strong");
          nome.textContent = aluno.nome;
          const detalhe = document.createElement("small");
          detalhe.textContent = aluno.detalhe;
          li.append(nome, detalhe);
          li.addEventListener("mousedown", (e) => { e.preventDefault(); escolher(aluno); });
          lista.append(li);
        });
      }
      lista.hidden = false;
      busca.setAttribute("aria-expanded", "true");
      ativo = -1;
      if (dados.total > itens.length) {
        ajuda.textContent = `${dados.total} alunos encontrados. Continue digitando para refinar.`;
      } else if (dados.total === 1) {
        ajuda.textContent = "1 aluno encontrado. Clique nele (ou aperte Enter) para escolher.";
      } else {
        ajuda.textContent = `${dados.total} aluno${dados.total === 1 ? "" : "s"} encontrado${dados.total === 1 ? "" : "s"}.`;
      }
    };

    const consultar = async () => {
      const texto = busca.value.trim();
      if (texto.length < 2) {
        fechar();
        ajuda.textContent = AJUDA_INICIAL;
        return;
      }
      const minha = ++sequencia;
      try {
        const resp = await fetch(`${raiz.dataset.url}?q=${encodeURIComponent(texto)}`, {
          headers: { Accept: "application/json" }, credentials: "same-origin",
        });
        if (!resp.ok) throw new Error(resp.status);
        const dados = await resp.json();
        if (minha === sequencia) desenhar(dados); // ignora respostas antigas
      } catch (erro) {
        ajuda.textContent = "Não foi possível buscar agora. Tente de novo.";
      }
    };

    busca.addEventListener("input", () => {
      clearTimeout(temporizador);
      temporizador = setTimeout(consultar, 180);
    });

    busca.addEventListener("keydown", (e) => {
      const aberta = !lista.hidden && itens.length > 0;
      if (e.key === "ArrowDown" && aberta) { e.preventDefault(); marcar((ativo + 1) % itens.length); }
      else if (e.key === "ArrowUp" && aberta) { e.preventDefault(); marcar((ativo - 1 + itens.length) % itens.length); }
      else if (e.key === "Enter" && !lista.hidden) {
        e.preventDefault(); // não envia o formulário enquanto a lista está aberta
        if (aberta) escolher(itens[ativo >= 0 ? ativo : 0]);
      } else if (e.key === "Escape") { fechar(); }
    });

    busca.addEventListener("blur", () => setTimeout(fechar, 120));

    if (trocar) {
      trocar.addEventListener("click", () => {
        oculto.value = "";
        selecionado.hidden = true;
        areaBusca.hidden = false;
        busca.value = "";
        ajuda.textContent = AJUDA_INICIAL;
        busca.focus();
      });
    }
  };

  document.addEventListener("DOMContentLoaded", () =>
    document.querySelectorAll("[data-aluno-autocomplete]").forEach(iniciar));
})();
