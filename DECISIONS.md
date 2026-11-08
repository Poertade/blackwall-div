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
