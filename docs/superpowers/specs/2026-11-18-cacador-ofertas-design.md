# Caçador de Ofertas — documento de projeto

*Versão 3 · 18/11/2026 · status: aprovado pelo Murilo (com AMD incluída nos processadores)*

## 1. O que é e por quê

Uma ferramenta pessoal que acompanha sozinha os preços de hardware gamer, iPhones e controles de console nas principais lojas brasileiras. Ela compara cada preço com o do Compras Paraguai e avisa no celular quando aparece uma promoção que vale a pena.

O motivo é não perder oferta boa (inclusive as relâmpago de madrugada) sem precisar ficar olhando loja por loja. O sistema também precisa mostrar se o "desconto" é real, comparando com o histórico de preço, e se vale mais a pena comprar no Paraguai.

O sistema tem três partes:
1. **Robô de coleta**, que roda na nuvem e confere os preços várias vezes por dia, mesmo com o PC desligado.
2. **Site**, onde o Murilo consulta tudo: abas por categoria, preço Brasil × Paraguai, histórico e cupons.
3. **Alertas no celular**, enviados quando uma oferta passa nos critérios.

## 2. O que entra (definido pelo Murilo)

| Categoria | Recorte |
|---|---|
| Placas de vídeo | RTX 3060 Ti em diante (série 30), toda a série 40 e toda a série 50 |
| iPhone | 15 em diante, com prioridade para Pro e Pro Max (modelos comuns só se o preço for muito bom). Novo e seminovo em listas separadas |
| Processadores | Intel e AMD |
| Placas-mãe | Só Asus e Gigabyte |
| Memória RAM | DDR4 e DDR5 |
| Periféricos | Headset, teclado e mouse, só Corsair e Logitech |
| Controles | PS5 (DualSense / DualSense Edge) e Xbox Series S/X |
| Cupons | Aba própria |

**Lojas:** Kabum, Pichau, Terabyte, Amazon, Mercado Livre, AliExpress e Shopee (as duas últimas só com vendedor confiável).
**Comparação:** Compras Paraguai.

## 3. Objetivos, o que não é, e o que seria fracasso

**Objetivos**
- Preço atual por produto e loja, com histórico de pelo menos 90 dias.
- Dizer se a oferta é real: comparar com a média de 30 dias e com o menor preço em 90 dias.
- Mostrar o preço no Paraguai convertido em reais, lado a lado.
- Alertar rápido no celular.
- Ter uma aba de cupons válidos para as lojas monitoradas.

**O que não é (fora do escopo da v1)**
- Comprar pelo site ou guardar dados de pagamento.
- Ganhar dinheiro com links de afiliado.
- Outras categorias, marcas ou lojas além das listadas.
- App de celular instalável (o site funciona no celular pelo navegador).

**O que seria fracasso, mesmo funcionando**
- Alerta demais: se o celular apitar a toda hora, o Murilo vai ignorar ou silenciar.
- Desconto falso: alertar "promoção" de preço que subiu antes de cair.
- Golpe: indicar placa de vídeo ou iPhone falsificado da Shopee ou do AliExpress como oportunidade.
- Comparação enganosa com o Paraguai, mostrando o preço sem deixar claro que não inclui imposto, cota e viagem.
- Site poluído ou com cara de template.

## 4. Restrições

- **Custo:** zero ou quase zero por mês. Usar o plano gratuito dos serviços.
- **Usuário leigo em programação:** depois de pronto, ajustar coisas comuns (produto acompanhado, preço-alvo, liga/desliga de alerta) tem que ser possível pela tela, sem mexer em código. Configurações iniciais precisam de passo a passo simples.
- **Lojas bloqueiam robôs:** cada loja precisa ser testada antes de ser prometida. Se uma não funcionar, isso aparece na tela ("loja sem atualização desde…") e não falha em silêncio.
- **Compras Paraguai não tem API pública:** a leitura depende do site deles e pode quebrar. É a parte de maior risco técnico.
- **Respeito às lojas:** consultas espaçadas, sem sobrecarregar os sites.

## 5. Caminhos considerados

| Caminho | Prós | Contras |
|---|---|---|
| **A) Nuvem com robô agendado** ✅ escolhido | Funciona com o PC desligado, guarda histórico, alerta a qualquer hora, de graça ou quase | Mais partes para montar. Algumas lojas bloqueiam robôs na nuvem |
| B) No PC do Murilo | Simples e sem custo | Só funciona com o PC ligado, perde ofertas de madrugada |
| C) Ler sites de ofertas prontos (Pelando, Promobit, Zoom) | Rápido e já traz cupons | Preço impreciso e atrasado, não cobre o Paraguai nem o histórico próprio |

**Escolhido pelo Murilo: A.** Por sugestão minha, o caminho C entra só como fonte de cupons.

## 6. Como funciona (decisões técnicas, chamadas minhas)

*Decisões que eu tomei e o Murilo pode mudar.*

**Onde cada parte roda**
- **Banco de dados:** Supabase (já conectado), guardando produtos, preços com data, lojas, cupons e alertas enviados.
- **Robô de coleta:** tarefa agendada em nuvem gratuita (GitHub Actions ou Cloudflare). Algumas lojas exigem um "navegador de verdade" para ler o preço, e o GitHub Actions aguenta isso melhor. A escolha final fica com quem constrói, depois de testar as lojas.
- **Site:** página publicada que lê os dados do banco.
- **Câmbio:** cotação do dólar de uma fonte pública e gratuita, atualizada junto com a coleta.

**Frequência:** placas de vídeo e iPhones a cada 1 hora. O restante a cada 3 horas. Cupons a cada 2 horas.

**Como os produtos são reconhecidos**
- Cada produto acompanhado é um "modelo" (ex.: "RTX 4070 Super 12GB", "iPhone 16 Pro 256GB"), e cada anúncio de loja é ligado a um modelo.
- Para iPhone, a capacidade separa os modelos (128/256/512 GB/1 TB). A cor não separa.
- Para placa de vídeo, o modelo do chip e a memória definem o modelo. A marca da placa (Asus, Gigabyte, MSI…) aparece no anúncio, mas o preço é comparado no nível do chip.
- Para CPU, placa-mãe, RAM e periféricos, que têm muitos modelos, o robô acompanha o que estiver em promoção dentro do recorte de marca e tipo. Não monta catálogo completo.
- Anúncio que o robô não conseguir encaixar com segurança vai para uma lista "não reconhecidos" e não gera alerta.

**Quando uma oferta é "boa" (critério de alerta)**
O alerta sai se a oferta cumprir pelo menos um destes:
1. O preço ficou igual ou abaixo do **preço-alvo** que o Murilo definiu para aquele produto.
2. É o **menor preço em 90 dias** e está pelo menos **10% abaixo da média de 30 dias**.
3. O preço caiu **15% ou mais** em relação ao dia anterior (promoção relâmpago).

Para evitar alerta demais:
- No máximo 1 alerta por produto a cada 12 horas, a não ser que o preço caia de novo.
- Resumo diário opcional às 20h com o que caiu, sem apitar o dia todo.
- Os produtos sem histórico ainda (primeiros dias) não disparam pelos critérios 2 e 3.

**Vendedor confiável (AliExpress e Shopee)**
- Aceito: loja oficial da marca, ou vendedor com nota ≥ 4,8 e mais de 1.000 vendas.
- Para placa de vídeo e iPhone a regra é mais rígida: só loja oficial. Preço mais de 30% abaixo da média das lojas brasileiras recebe a marca "⚠ risco de golpe" e nunca gera alerta.

**Comparação com o Paraguai**
- Preço em dólar, convertido para reais pela cotação do dia.
- Sempre com o aviso "sem impostos, cota e custo de viagem".
- Se o Compras Paraguai não puder ser lido, a coluna mostra "indisponível" e o resto do site continua funcionando.

**Cupons**
- Vindos de sites de ofertas (Pelando, Promobit) e das páginas de cupom das próprias lojas, filtrados para as lojas monitoradas.
- Cada cupom mostra a loja, o código, a validade (quando houver) e quando foi visto pela última vez.

## 7. O site

**Para que serve:** consultar com calma, configurar preço-alvo e ver os cupons. Os alertas cuidam do "não perder a hora".

**Telas**
1. **Início:** as melhores quedas do momento (no máximo 6) e o status do robô (última atualização).
2. **Categoria (uma aba por categoria):** lista de modelos com preço Brasil (melhor loja), preço Paraguai, variação e menor em 90 dias.
3. **Produto:** gráfico do histórico, preço em cada loja, preço Paraguai, botão "avisar se ficar abaixo de R$ ___" e liga/desliga de alerta.
4. **Cupons:** lista por loja.
5. **Ajustes:** liga/desliga de alerta por categoria, horário do resumo diário e status de cada loja (funcionando ou com problema).

**Direção visual (seguindo a skill de design)**
- **Ideia condutora: "gravidade do preço".** Cada produto é uma esfera de luz flutuando na altura do seu preço. Quando o preço cai, ela desce. Encostar no "chão" (o menor preço em 90 dias) faz ela acender. A página inicial é essa cena em 3D: as quedas do momento caindo em câmera lenta sobre um piso de grade. O mesmo movimento se repete nos detalhes: o gráfico de histórico é o rastro da queda, e o botão de alerta "puxa" a esfera para baixo quando você define o preço-alvo.
- **Tipografia:** títulos e preços em fonte condensada pesada, com cara de etiqueta de preço (ex.: Big Shoulders Display). Texto em sans limpa (ex.: Manrope).
- **Paleta "coral etiqueta" (escolhida pelo Murilo):** fundo papel `#F4F1EC`, brilho coral `#FF4D4D`, apoio tinta `#2B2B2B`. O fundo é claro, então as esferas não "brilham no escuro": elas aparecem como gotas de coral com sombra macia no piso. A queda fica marcada pela sombra que cresce. *Chamada minha:* o coral puro tem contraste baixo para texto pequeno (2,9:1). Ele fica para esferas, números grandes e destaques, e o texto pequeno em coral usa o tom mais escuro `#C62828` (5:1). A cor fica numa variável só, para trocar fácil.
- **Tela limpa:** um protagonista por tela, no máximo 6 destaques no início e o resto nas abas.
- **Acessibilidade:** respeitar quem desativa animações, contraste mínimo de 4,5:1 e botões grandes no celular.
- Funciona bem no celular, porque o alerta vai levar para lá.

## 8. Alertas

- **Bot do Telegram, como o Murilo escolheu** (de graça e estável). A mensagem traz o produto, o preço, a loja, o motivo do alerta ("menor em 90 dias"), o preço no Paraguai, um cupom aplicável quando houver e o link.
- **WhatsApp depois (opcional):** API oficial da Meta. No Brasil, custa cerca de R$ 0,035 por mensagem de utilidade e R$ 0,32 por mensagem de marketing (tabela de out/2026). Um alerta de promoção tende a ser classificado como marketing. Com uns 5 alertas por dia, ficaria entre R$ 5 e R$ 50 por mês. A alternativa não oficial é gratuita, mas pode levar ao banimento do número e não é recomendada.

## 9. O que fica para quem constrói

- Como ler cada loja (API, página ou navegador simulado), testando uma a uma.
- A estrutura exata das tabelas do banco.
- Os textos finais das telas e dos alertas, seguindo este documento.
- A ordem de entrega sugerida: (1) banco + robô com Kabum, Pichau e Terabyte; (2) site; (3) alertas Telegram; (4) Amazon, Mercado Livre e Paraguai; (5) AliExpress, Shopee e cupons.

## 10. Chamadas minhas feitas na revisão

- **Controles:** só originais (Sony e Microsoft). Os de outras marcas ficam de fora.
- **Periféricos Logitech:** linha gamer (Logitech G) e também os comuns de teclado e mouse, desde que sejam headset, teclado ou mouse.
- **Contas necessárias:** o Murilo vai precisar criar contas gratuitas (GitHub, bot do Telegram) com um passo a passo guiado. Nenhum cartão de crédito é necessário.

## 11. Respostas do Murilo na revisão

- **Quem usa:** só o Murilo. O site é protegido por uma senha simples e há um único bot de alertas. Sem cadastro de usuários.
- **Paleta:** coral etiqueta (ver seção 7).
- **iPhone:** novo e seminovo, **em listas separadas** e nunca comparados entre si. Seminovo/recondicionado exige vendedor confiável (seção 6) em qualquer loja, inclusive no Mercado Livre. Seminovo só gera alerta pelo preço-alvo ou pelo menor preço em 90 dias da própria lista de seminovos. A Apple Recondicionado oficial, se aparecer, entra como seminovo confiável.
- **Alertas:** Telegram.
