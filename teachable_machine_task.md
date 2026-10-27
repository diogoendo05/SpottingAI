# Task: Implementação da Aba Teachable Machine (TV Layout)

**Contexto para o Claude:** 
O projeto `SentinelAI` (ou `SpottingAI`) é uma plataforma de videoanalítica. Precisamos adicionar uma nova funcionalidade (aba) no frontend (`static/index.html` e `static/css/style.css`) focada em educar alunos durante uma oficina prática. Essa aba será exibida em uma **TV de tela grande**, logo a tipografia, contraste e o layout precisam ser excelentes, modernos e muito legíveis à distância.

## 🎯 Objetivo
Adicionar uma nova aba de navegação lateral chamada **"Laboratório AI"**. Ao clicar nela, o painel principal deve exibir um passo a passo interativo para os alunos usarem a ferramenta do Google (Teachable Machine) para treinar um modelo de visão computacional próprio.

## 🎨 Requisitos de Layout (Design para TV)
1. **Tipografia Grande:** Usar fontes grandes (ex: `font-size: 2rem` para textos base, e `3.5rem` ou `4rem` para títulos).
2. **Cards / Passos Visuais:** O conteúdo não deve ser um texto corrido chato. Use um layout em Grid ou Flexbox com "Cards" enumerados (Passo 1, Passo 2, Passo 3). Cada card deve ocupar boa parte da tela para leitura fácil de longe.
3. **Cores e Contraste:** O projeto usa um tema escuro (`#0A0C11`). Use as variáveis de cor existentes no `style.css` (como `--primary`) e aplique cores de destaque vibrantes para os botões e números dos passos.
4. **Call to Action:** Um botão gigante e estilizado que abre o [Teachable Machine](https://teachablemachine.withgoogle.com/train/image) em uma nova aba (`target="_blank"`).

## 📝 O Conteúdo (Passo a Passo)
Adicione o seguinte conteúdo HTML dentro da nova aba (formate usando as tags semânticas adequadas e classes de CSS para os Cards de TV):

*   **Título Principal:** Treine sua própria Inteligência Artificial!
*   **Subtítulo:** Ensine a máquina a reconhecer você com ou sem objetos (ex: mochila, óculos ou boné).

*   **📸 Passo 1: O Combustível da IA (Imagens)**
    *   **Texto:** A IA aprende por exemplos. Acesse o Teachable Machine clicando no botão abaixo. Na "Class 1", ative a Webcam e tire 30 fotos suas **sem nada**. Na "Class 2", tire 30 fotos suas **usando óculos** ou **mochila**. Mude o ângulo e a luz!
    *   **Ação:** Um botão ou link gigante -> "🚀 ABRIR TEACHABLE MACHINE" (`href="https://teachablemachine.withgoogle.com/train/image"` `target="_blank"`)

*   **🧠 Passo 2: O Treinamento (A Mágica)**
    *   **Texto:** Agora que você deu os exemplos, clique no botão **"Train Model"** no site do Google. A máquina vai analisar os pixels das suas fotos milhares de vezes para encontrar padrões. *Dica: Não mude de aba durante o treinamento!*

*   **🎯 Passo 3: O Teste de Fogo (Inferência)**
    *   **Texto:** A IA já aprendeu? Na coluna de "Preview", teste ao vivo! Coloque e tire os óculos ou mochila e veja se a porcentagem acerta. Tente "enganar" a IA usando a mochila de um colega!

## 🛠️ Instruções Técnicas (Tasks para Execução)
1. **Atualizar `static/index.html`**:
   - Adicionar o botão no menu de navegação lateral (tag `<nav id="sidebar">`). Use o ícone SVG `#i-book` ou crie um novo.
   - Adicionar o container de conteúdo: `<section id="view-teachable" class="view-section hidden">...</section>`.
   - Adicionar o HTML dos títulos e dos 3 cards de instrução dentro deste novo `<section>`.
   - Garantir que o link do menu chame a função JS existente (se houver) ou adicione a lógica de clique para ocultar as outras `.view-section` e mostrar a `#view-teachable` removendo a classe `.hidden`.

2. **Atualizar `static/css/style.css`**:
   - Criar as classes `.tv-card-container` (para um Grid/Flex), `.tv-card`, `.tv-title`, `.tv-text` e `.tv-btn-large`.
   - Ajustar os tamanhos de fonte, `padding` e `gap` para que fique excelente em uma resolução Full HD (1920x1080).
