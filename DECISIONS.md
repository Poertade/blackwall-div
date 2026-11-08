# Decisões do Blackwall Dive

### 2026-11-07: o jogo "de verdade"
- **O pedido:** depois do incremental em HTML, um jogo com executável:
  - em ondas, como Seabun;
  - com ups que guiam para uma build;
  - com os quickhacks do Cyberpunk 2077;
  - com uma quest line de três caminhos: solo, equipe netrunner e Netwatch.
- **As respostas, uma por uma** (o desenho inteiro está em [docs/GDD.md](docs/GDD.md)):
  - **Plataforma:** Python com pygame (pygame-ce). O .exe sai pelo PyInstaller no GitHub Actions.
  - **Controle pelo mouse:** segurar o botão esquerdo anda até o cursor. Os hacks não são automáticos: saem pelas teclas, no ICE sob o cursor. No máximo uma skill ataca sozinha, e ela muda com a build.
  - **Cenário:** o ciberespaço. Os nomes são os originais do 2077 (Night City, Netwatch, Ed, os quickhacks, os cyberdecks, os Black ICE). Os personagens são novos, no mundo do 2077.
  - **As builds, todas as quatro:**
    - Contágio (espalhar o dano);
    - Sobrecarga (dano alto, pouca cadência);
    - Cadeia (rápido);
    - Controle e execução.
  - **Escolher uma build deixa ela bem mais forte, mas não trava os outros hacks:** os bônus de tag só somam nos hacks daquela tag, e os outros continuam com o valor de base.
  - **A progressão:** ups dentro do mergulho e uma árvore permanente que só mexe em números.
  - **Hacks e decks:** vêm das camadas, da quest line e de uma loja paga com Ed. Há cyberdecks com mais slots.
  - **Os modos, todos:** camadas de 10 ondas com chefe, ondas infinitas e missões curtas da história.
  - **O caminho da história:** é escolhido depois da 1ª camada e é definitivo por salvamento. A equipe coleta Ed no mergulho e fora dele.
- **As perguntas em aberto ficaram com a proposta do documento:**
  - **Os personagens:** Rhyme, Juno Takeda e a Agente Halloran.
  - **O flatline:** perde 25% do Ed do mergulho.
  - **O deck inicial:** tem 2 slots.
  - **Os números dos caminhos:** solo +25%, Netwatch +12%, equipe com aliados e renda.
  - Tudo isso está nos arquivos YAML, para ajustar sem mexer no código.
- **O repositório** é `blackwall-div`. O nome saiu com um erro de digitação e ficou assim, a pedido do usuário. O incremental em HTML ficou só no `desktop-tutorial`.

### Como o jogo é montado
- **A simulação é separada da tela** (`blackwall/sim`):
  - os testes, o robô de balanceamento e o jogo rodam o mesmo código;
  - o mergulho é determinístico com a mesma semente;
  - o passo é fixo em 1/60 s.
- **Tudo que melhora a netrunner é escrito do mesmo jeito** (`stats`, `tag_damage`, `hacks`, `flags`): os ups, os bônus de build, a árvore, os decks e os caminhos. Uma única classe soma tudo.
- **O conteúdo está em YAML** e é conferido ao abrir: um nome errado num up ou numa camada para o jogo com uma mensagem clara.
- **O visual em neon:**
  - as formas são desenhadas duas vezes, na tela e numa camada de brilho;
  - o brilho é borrado em meia resolução e somado à tela;
  - os sons são sintetizados na hora, sem arquivos.

### As regras que saíram do desenho
- **A mira assistida:** o hack vai no ICE mais perto do cursor, dentro de 80 px. Assim não é preciso acertar o pixel.
- **O upload:** os hacks levam um tempo para chegar, como no 2077 (Short Circuit 0,15 s, System Collapse 1 s). Se o alvo morre no caminho, a RAM volta.
- **Os chefes resistem a controle:** os controles duram 30% do normal. Memory Wipe, Cyberpsychosis e Reboot Optics não funcionam neles (Cyberpsychosis devolve metade da RAM).
- **O deck escolhe as builds possíveis:** um up de build só aparece se algum hack do deck for daquela tag. Assim não aparecem ups mortos, e montar o deck já é escolher a build.
- **Entre as ondas:**
  - a Integridade e a RAM voltam inteiras, como no Brotato;
  - o perigo é de cada onda;
  - o roubo de vida e a regeneração contam dentro dela.
- **Desconectar:** entre as ondas, volta com todo o Ed. No meio da onda (Esc → cortar a conexão, ou fechar o jogo), perde 25%, como no flatline.

### O ritmo medido (tools/simular.py)
- **O robô:**
  - foge da soma das ameaças perto (ICE, tiros, poças);
  - lança o hack pronto no melhor alvo (área no grupo maior, dano alto no mais forte);
  - escolhe os ups da tag que mais pegou;
  - entre um mergulho e outro, compra decks maiores, os hacks que entrariam no deck e o nó mais barato da árvore.
- **Primeira medição:** ele travava na camada 4.
  - A árvore tinha nós curtos (máximo de 10 níveis).
  - Com tudo comprado, não havia mais como crescer: 90 mergulhos morrendo na mesma onda.
  - **A mudança:** Dano, Integridade e RAM de volta vão até 30 a 40 níveis, encarecendo 20% a cada nível, e as camadas multiplicam menos a vida dos ICE (1; 1,8; 3; 4,6; 6). Num incremental, insistir sempre tem que ajudar.
- **Segunda medição:** os chefes das camadas 2 (Agente Kessler) e 4 (Giant) eram paredes, com 10 e 26 mortes seguidas na 10ª onda.
  - **A mudança:** menos vida, rajadas mais lentas e cargas com mais aviso.
- **Agora (média de 3 carreiras do robô):**

  | Camada | Mergulhos (acumulados) | Minutos (acumulados) |
  |---|---|---|
  | 1 | ~2 | 9 |
  | 2 | ~14 | 57 |
  | 3 | ~22 | 94 |
  | 4 | ~47 | 197 |
  | 5 | ~78 | 361 |

  Uma pessoa mira pior que o robô, mas monta builds melhores.
- **O bug que o robô achou:** o Liche morrendo envenenado limpava os efeitos no meio do laço que os percorria e derrubava o jogo. Corrigido, e há um teste para isso.

### 2026-11-08: a quest line (marco 5)
- **O caminho é escolhido na aba HISTÓRIA**, depois da 1ª camada, com dois cliques: o segundo confirma ("é para sempre"). A 2ª camada só abre depois da escolha; a narrativa não é opcional, e o salvamento não fica sem caminho.
- **O Netdriver MK.5 vem na hora**, ao escolher a Netwatch (no documento era "deck próprio"). A primeira missão da Netwatch paga Weapon Glitch.
- **As missões usam os mesmos ICE e as mesmas ondas das camadas**, com um objetivo por cima:
  - **download:** um nó parado no meio; o ICE corpo a corpo vai atrás dele quando ele está mais perto que você;
  - **escolta:** o mesmo nó, andando de um lado ao outro durante a missão;
  - **nós:** a onda não termina enquanto os nós dela estiverem de pé, e cada nó solta um Wisp a cada 7 s;
  - **caçada:** o alvo (Kurogane, Severin) aparece na última onda, como um chefe;
  - **aguentar:** só sobreviver.
- **Missão falha não é flatline:** se o nó cai, você volta com todo o Ed, só sem a recompensa.
- **Os aliados não critam e não têm build**, mas escalam com o nível (+20% por nível) e com o dano geral da árvore. A Mira cura e devolve RAM. O Ruído atordoa o maior grupo. A Juno e o Varga causam dano.
- **A renda:**
  - corre enquanto você não está mergulhando: no esconderijo, em tempo real; com o jogo fechado, pelo tempo desde o último salvamento, até 12 horas;
  - no mergulho não corre, porque a equipe está com você recolhendo o Ed;
  - a da equipe é maior que o salário da Netwatch; o solo não tem renda.
- **Os nomes novos:**
  - Bento "Ruído" Okafor e Mira Solano, da equipe;
  - o Agente Varga;
  - o Agente Kessler, chefe da camada 2;
  - Kurogane, caçador da Arasaka;
  - Severin, dos Voodoo Boys.

### O ritmo por caminho (o robô, 2 carreiras cada, só camadas)
- O robô escolhe o caminho depois da 1ª camada. Ele não faz missões, não treina a equipe e não fica parado ganhando renda. Então a equipe rende mais numa pessoa do que aqui.
- **Os minutos acumulados até vencer cada camada:**

  | Caminho | 1 | 2 | 3 | 4 | 5 |
  |---|---|---|---|---|---|
  | Solo | 10 | 42 | 61 | 123 | 187 |
  | Equipe | 10 | 43 | 63 | 132 | 198 |
  | Netwatch | 10 | 34 | 70 | 115 | 163 |

- **O Giant ainda era a maior parede** (12 mortes seguidas): ficou com menos vida, uma carga mais avisada e menos invocações. Agora a parede maior é a IA renegada, o chefe final, como deve ser.

### 2026-11-08: a trilha do primeiro jogo e a primeira versão
- **O pedido:** criar o executável e usar a trilha do primeiro jogo (o projeto-netrunner).
- **Os três loops vieram como estão** (`assets/music/`, composições originais daquele projeto), um por clima:
  - o apartamento no esconderijo;
  - a rede "com defeito" nas ondas;
  - a perseguição quando há chefe ou alvo de caçada na arena.
- **A troca entre eles** é em fade: meio segundo para sair, um para entrar.
- **O mixer passou a estéreo**, para manter o estéreo das trilhas.
- **F3** liga e desliga só a música; **F2** continua para os efeitos.
- **O executável:** cada envio gera os zips do Windows e do Linux nos artefatos do Actions. Uma tag `v*` também publica os zips na página de Releases. A tag fica a cargo do usuário, porque publicar uma release é uma ação dele.

### 2026-11-08: a primeira rodada de testes do usuário
**O que o usuário pediu, depois de jogar o .exe:**
1. tela cheia sem pixelizar;
2. os efeitos de ataque pararam do nada e voltaram;
3. os ups do mergulho só com números (Integridade, dano, recarga);
4. os efeitos especiais (saltos, alvos extras) numa árvore própria de cada hack;
5. os nós bloqueados da árvore ocultos;
6. a HISTÓRIA parecida com o celular (o Mensageiro) do primeiro jogo;
7. as ondas acabando só quando todos os ICE caem;
8. o movimento como hack, com variações e custo de RAM.

**Perguntas e respostas:**
- O movimento ocupa um slot do deck, e todos os decks ganharam um slot a mais.
- As variações são as quatro: Andar, Kerenzikov, Teleporte e Sandevistan.
- A árvore de cada hack é permanente, comprada com Ed.
- Cada onda tem quantidade fixa de ICE, com reforços se demorar.

**O que mudou:**
- **A tela cheia:** o SDL escala a tela lógica com filtro linear (`SDL_RENDER_SCALE_QUALITY`), sem pixelizar.
- **Os efeitos que sumiam eram o som.** O mixer tinha 8 canais, e numa onda cheia todos ficavam ocupados até os sons longos acabarem. Agora são 32 canais, e os sons importantes (lançar, levar dano, onda, chefe) tomam o canal do som mais velho.
- **O "ª" (e o "º") não existem na fonte Rajdhani** e apareciam como um quadrado ("1□ camada"). Os textos usam "primeira" e "quinto".
- **O movimento:**
  - O botão esquerdo usa o primeiro hack de movimento do deck; a tecla do slot também funciona.
  - Andar e Sandevistan gastam RAM por segundo enquanto você se move; sem RAM, a netrunner para.
  - O Kerenzikov e o Teleporte gastam RAM por uso e têm recarga.
  - O Sandevistan desacelera o mundo inteiro (ICE, tiros, chegada das ondas), mas não a netrunner nem a RAM.
  - Os saves antigos ganham o Andar no slot 1.
- **Os ups:**
  - São 28, só números, com tag. Entraram `tag_cooldown` (a recarga mais rápida só dos hacks de uma tag) e os ups de dano por tag.
  - Os bônus de conjunto (2/4/6) e o ataque automático de cada build ficaram.
- **As árvores dos hacks** (`data/hack_trees.yaml`):
  - têm 56 nós, de 2 a 4 por hack, inclusive os de movimento;
  - receberam os efeitos especiais que eram ups: Arco extra, Mutação, Epidemia, Paciente zero, Fagulha, Execução, Cegueira, Eco sônico, Burnout, Imunodeficiência, Vulnerável;
  - o Overclock saiu.
- **A aba ÁRVORE:** escolhe a árvore numa coluna à esquerda (Netrunner ou um hack). Mostra o nível com número e barra contínua, porque os 40 tracinhos ficavam ilegíveis. Os nós cujo nó de cima ainda não foi comprado ficam ocultos, com uma linha dizendo quantos faltam revelar.
- **As ondas:**
  - O começo de cada onda sorteia a lista inteira de ICE: o orçamento de antes, distribuído pelo tempo de chegada.
  - A onda acaba quando todos chegaram e caíram.
  - Passados 20 s depois do tempo de chegada, vem um reforço a cada 7 s.
  - O chefe continua acabando a onda dele.
  - O download e a escolta andam conforme as ondas vencidas e os ICE derrubados.
- **A HISTÓRIA virou o Mensageiro:**
  - à esquerda, os contatos: avatar quadrado com a inicial, prévia e não lidas;
  - à direita, os balões, um por linha da fala;
  - as missões chegam como "SERVIÇO" na conversa de quem passa o trabalho;
  - embaixo, as respostas numeradas, como no primeiro jogo: a escolha do caminho com dois cliques e o "ACEITAR SERVIÇO";
  - a equipe tem a própria conversa, com o treino de cada membro.
- **O ritmo:**
  - Com todo ICE precisando cair, o orçamento das ondas caiu de 1,3 para 0,6 por segundo.
  - A RAM de volta subiu de 1,8 para 2,2, porque andar também gasta.
  - O robô (2 carreiras por caminho) vence a primeira camada em ~2 mergulhos e o jogo em 1h45 (Solo e Netwatch) a 2h40 (Equipe; o robô não treina a equipe nem fica parado ganhando a renda).

### 2026-11-08: a segunda rodada de testes
**O que o usuário pediu, e o que mudou:**
1. **"O jogo está fácil demais":**
   - **Os Wisps:** agora atiram em você, com um tiro lento e teleguiado que vira atrás da netrunner (2 rad/s) e dura 4,5 s.
   - **Os grupos:** chegam com o dobro de ICE de uma vez (o Wisp em grupos de 6 a 10).
   - **As ondas e as camadas:**
     - o total de ICE por onda subiu (orçamento de 0,6 para 0,95 por segundo);
     - a vida dos ICE cresce 16% a cada onda (eram 12%);
     - as camadas fundas ficaram mais duras (vida ×2,2 / ×4 / ×6,5 / ×9,5 e dano ×1,4 / ×1,9 / ×2,4 / ×3);
     - cabem até 120 ICE na arena.
2. **Os ups esperam meio segundo** depois da onda para aparecer. Antes disso, as teclas e os cliques não escolhem nada, para não pegar um up sem querer.
3. **O movimento é por destino:**
   - um clique marca o ponto, e a netrunner vai até lá sozinha, gastando a RAM por segundo do Andar (ou do Sandevistan) enquanto anda;
   - segurar o botão arrasta o destino;
   - o dash e o teleporte cancelam a caminhada;
   - um X ciano marca o destino na arena.
4. **O som que parava e voltava:**
   - **A causa:** o intervalo mínimo entre dois sons iguais usava o relógio da tela, que zera a cada mergulho, e no esconderijo era sempre 0. Os sons que tinham tocado num mergulho longo ficavam mudos no mergulho seguinte até o relógio novo passar do antigo.
   - **A correção:** o jogo usa um relógio que nunca volta (`time.monotonic`), e há um teste para isso.
   - **Os 32 canais** da rodada anterior continuam, mas não eram a causa.
5. **Nenhum hack de ataque recarrega em menos de 1 s:**
   - o Short Circuit foi de 0,5 s para 1 s, com o dano de 16 para 22;
   - os de movimento continuam livres;
   - toda árvore de hack de ataque ganhou o nó **Recarga** na raiz, sempre visível (-8% por nível, até 5 níveis = -40%), no lugar dos nós de recarga espalhados (Condutor, Ping rápido, Dissipador, Reinício, Pane rápida, Reciclagem, Gatilho e as Recargas).

**O ritmo (o robô, 2 carreiras por caminho):** a primeira camada sai em ~2,5 mergulhos (18 min). O jogo inteiro leva 2h20 no Solo e na Netwatch e 3h na Equipe.

### 2026-11-08: a terceira rodada de testes
- **A chegada dos ICE é mais rápida:** os mesmos ICE de cada onda chegam na metade do tempo (`arrival: 0.5`). Os reforços contam a partir daí, e os ICE que acompanham o chefe também vêm duas vezes mais rápido.
- **O "Netrunner da Netwatch" virou só "Netrunner".**
- **O dano de todos os ICE dobrou** (`enemy_damage: 2.0`): encostar, tiros, poças e ataques dos chefes. O roubo de RAM não mudou.
- **Medido com o robô:** ele precisava de ~35 mergulhos (1h25) para vencer a primeira camada e morria 22 vezes já na primeira onda, até a árvore permanente crescer. O jogo inteiro levava de 3h45 a 4h20.
- **A escolha do usuário:** suavizar só a primeira camada. Ela ganhou um `ramp: 0.35`: a onda 1 tem 35% dos ICE, subindo em linha reta até 100% na onda 10. As outras camadas, a chegada rápida e o dano em dobro ficaram como foram pedidos.
  - Agora o robô vai mais longe a cada mergulho: as mortes se espalham da onda 4 ao Kraken.
  - Ele leva ~18 mergulhos (1h) para vencer a primeira camada e ~3h15 para o jogo todo (Solo).
