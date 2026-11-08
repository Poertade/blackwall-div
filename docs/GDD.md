# Blackwall Dive: documento de desenho

O nome é provisório. Os itens marcados com **[decidido]** vieram das respostas do usuário; o resto foi proposta, aprovada em 2026-11-08 (as perguntas da seção 13 ficaram com as propostas). O que já está no jogo e o que mudou com o balanceamento estão em [DECISIONS.md](../DECISIONS.md).

## 1. O conceito

Night City, 2077. Você é uma netrunner freelancer. Do seu esconderijo, você mergulha no ciberespaço, camada por camada:

- a rede da cidade;
- as redes das corporações;
- a Old Net, as ruínas de antes do DataKrash;
- os arredores da Blackwall, o muro que a Netwatch ergueu para segurar as IAs renegadas;
- e, no fim, o outro lado.

Cada mergulho é uma sequência de **ondas** de ICE e programas hostis. Você sobrevive lançando **quickhacks** e volta com Ed para ficar mais forte. **[decidido]** É um survivor-like em ondas com progressão incremental, como Seabun, com o nome original de tudo do Cyberpunk 2077 (Night City, Netwatch, Ed, os quickhacks).

**Plataforma [decidido]:** Python com pygame. O .exe sai pelo GitHub Actions a cada envio (Windows e Linux), como no projeto-netrunner.

## 2. Os controles [decidido]

- **Segurar o botão esquerdo:** a netrunner anda atrás do cursor. Soltou, ela para, e o cursor fica livre para mirar.
- **Teclas 1, 2, 3...** (uma por slot do cyberdeck): lançam o quickhack daquele slot no inimigo sob o cursor. Para não exigir precisão de pixel, a mira escolhe o inimigo mais perto do cursor dentro de um raio pequeno. Hacks de área vão no ponto do cursor.
- **Ataque automático [decidido]:** só um, e ele muda com a build (seção 4).
- Esc pausa. Tab mostra a build (as tags e os bônus ativos).

## 3. O mergulho

- **Integridade** (a vida): zerou, é flatline. Você volta ao esconderijo com o Ed coletado *(proposta: perde 25% do Ed coletado nesse mergulho, para morrer pesar um pouco)*.
- **RAM:** cada hack gasta RAM, que volta com o tempo. É o ritmo do jogo: gastar tudo de uma vez ou dosar.
- **Ed:** cai dos inimigos como fragmentos de dado; passar perto recolhe.
- **Ondas:** cada uma dura de 30 a 45 segundos. Entre uma onda e outra, você escolhe **1 de 3 melhorias** (os "ups", seção 4). A cada 10 ondas, um **chefe**.

## 4. As builds (os ups dentro do mergulho) [decidido]

Cada up tem uma ou mais **tags**: Contágio, Sobrecarga, Cadeia, Controle (e alguns sem tag, que servem a qualquer build). Funciona assim:

- **Bônus da build:** juntar ups da mesma tag liga bônus de conjunto com 2, 4 e 6 ups. Com 3 ups da tag que você mais pegou, liga o **ataque automático** dela.
- **Guia:** as escolhas seguintes passam a oferecer mais ups da sua tag, como as tags do Brotato. É o que guia você para uma build.
- **Sem prender [decidido]:** escolher uma build a deixa bem mais forte, mas não trava os outros hacks. Eles continuam funcionando com os valores de base, e os ups sem tag melhoram todos.

### Contágio: espalhar o dano
- **Hacks centrais:** Contagion (e Overheat como apoio).
- **Ups de exemplo:**
  - *Mutação*: Contagion pula para +1 alvo.
  - *Incubação*: o veneno dura +2 s.
  - *Epidemia*: quem morre envenenado contamina quem está em volta.
  - *Imunodeficiência*: alvos envenenados tomam +15% de todo dano.
- **Bônus:** 2 ups dão +20% de dano de veneno; 4 fazem o veneno pular sozinho a cada 2 s; 6 fazem Contagion custar 0 RAM em quem já está envenenado.
- **Automático:** um rastro de veneno atrás da netrunner.

### Sobrecarga: dano alto, cadência baixa
- **Hacks centrais:** Synapse Burnout e Short Circuit.
- **Ups de exemplo:**
  - *Capacitor*: +40% de dano e +25% de recarga.
  - *Overclock*: gasta o dobro de RAM e o dano vai a 2,5 vezes.
  - *Pico de tensão*: +chance de crítico.
  - *Burnout*: mais dano quanto menos vida o alvo tem.
- **Bônus:** 2 ups dão +25% de dano por acerto; com 4, o crítico atordoa; com 6, cada 5º hack causa o triplo.
- **Automático:** a cada 3 s, uma descarga forte no inimigo com mais vida.

### Curto-circuito em cadeia: rápido
- **Hacks centrais:** Short Circuit e Overheat (e Blackwall Gateway, o supremo).
- **Ups de exemplo:**
  - +1 salto;
  - -1 de custo de RAM;
  - +20% de RAM de volta;
  - *Fagulha*: quem toma choque pega fogo (Overheat);
  - -15% de recarga.
- **Bônus:** 2 ups dão +1 salto; com 4, os saltos não perdem dano; com 6, cada salto devolve RAM.
- **Automático:** um arco que pula entre 3 inimigos próximos a cada segundo.

### Controle e execução
- **Hacks centrais:** Cripple Movement, Reboot Optics e Sonic Shock (e System Reset, o supremo).
- **Ups de exemplo:**
  - *Paralisia*: o Cripple Movement prende +1 s.
  - *Cegueira*: inimigos cegos erram os tiros.
  - *Vulnerável*: +30% de dano em quem está sob controle.
  - *Execução*: System Reset desliga quem não é chefe e está abaixo de 30% de vida.
- **Bônus:** 2 ups fazem os controles durarem +30%; com 4, matar um inimigo controlado devolve RAM; com 6, inimigos controlados abaixo de 15% de vida caem na hora.
- **Automático:** um campo em volta da netrunner que deixa os inimigos 30% mais lentos.

**Ups sem tag:** +Integridade, +RAM, roubo de vida, velocidade, ímã de Ed, armadura, -recarga de tudo.

## 5. Os quickhacks (nomes do Cyberpunk 2077)

| Quickhack | Tipo | O que faz no jogo |
| --- | --- | --- |
| **Short Circuit** | combate | dano elétrico no alvo |
| **Ping** | furtivo | marca os inimigos de uma área: +20% de dano neles por 5 s |
| **Overheat** | combate | queima o alvo (dano por segundo) |
| **Contagion** | combate | veneno que pula para os inimigos perto |
| **Synapse Burnout** | combate | dano alto, maior quanto menos vida o alvo tem |
| **Cripple Movement** | controle | imobiliza o alvo |
| **Reboot Optics** | controle | cega o alvo: perde você de vista e erra |
| **Sonic Shock** | controle | atordoa numa área pequena |
| **Weapon Glitch** | controle | quem é atingido causa menos dano |
| **Memory Wipe** | furtivo | o alvo fica confuso e ataca os outros ICE |
| **Cyberpsychosis** | supremo | o alvo ataca tudo em volta |
| **Detonate Grenade** | supremo | explosão em área |
| **System Reset** | supremo | desliga um inimigo que não é chefe |
| **Blackwall Gateway** | supremo | um raio da Blackwall que salta entre muitos inimigos |
| **System Collapse** | supremo | destrói o alvo (chefes tomam um dano enorme) |

- **Começo:** Short Circuit e Ping.
- **Hacks novos [decidido]:** vêm ao vencer camadas e passos da quest line, e a **loja** vende os que ainda faltam, por Ed.

## 6. Os cyberdecks [decidido: há decks com mais slots]

| Cyberdeck | Slots | Bônus | Como ganha |
| --- | --- | --- | --- |
| Militech Paraline | 2 | nenhum | o seu primeiro |
| Biotech Σ MK.1 | 3 | +10% de RAM de volta | loja |
| Fuyutsuki Tiny Ninja | 3 | controles duram +20% | loja |
| Raven Microcyber MK.3 | 4 | Contagion pula +1 | loja |
| Tetratronic Rippler MK.4 | 4 | +10% de chance de crítico | loja |
| Arasaka MK.4 | 5 | -10% de custo de RAM | loja, depois da camada 3 |
| Netwatch Netdriver MK.5 | 6 | +15% de dano em IAs e netrunners | caminho Netwatch |
| Militech Canto MK.6 | 6 | supremos custam 25% menos | loja, depois da camada 4 |

Antes de cada mergulho, você escolhe o deck e quais hacks vão nos slots.

## 7. A progressão permanente [decidido: só números]

Uma árvore no esconderijo, paga com Ed. Cada nó sobe de nível e só mexe em valores:

- dano;
- Integridade;
- roubo de vida;
- RAM máxima e RAM de volta;
- velocidade;
- chance e dano de crítico;
- armadura;
- alcance de coleta;
- Ed por inimigo;
- duração dos efeitos;
- recarga.

Os hacks e os decks ficam fora da árvore: vêm da loja e da história.

## 8. Os inimigos

Os nomes vêm dos Black ICE clássicos do Cyberpunk:

| Inimigo | Papel |
| --- | --- |
| **Wisp** | enxame fraco, vem em bando |
| **Raven** | atira de longe |
| **Hellhound** | rápido, persegue |
| **Sabertooth** | tanque, investe em linha reta |
| **Asp** | deixa poças de veneno |
| **Scorpion** | paralisa quem encosta |
| **Netrunner** | um inimigo que hackeia você (rouba RAM, atrasa as recargas) |
| Chefes | **Kraken** (tentáculos), **Liche** (se reconstrói), **Giant**, um **agente da Netwatch** e a **IA renegada** do outro lado da Blackwall |

## 9. Os três modos [decidido: todos]

1. **Camadas:** cinco camadas de 10 ondas, com um chefe na 10ª. Vencer uma camada libera a próxima, um hack e um passo da história.
   1. A rede de Night City (subredes de Watson); chefe: Kraken.
   2. As redes corporativas (Arasaka, Militech); chefe: agente da Netwatch.
   3. A Old Net; chefe: Liche.
   4. Os arredores da Blackwall; chefe: Giant.
   5. O outro lado; chefe: a IA renegada.
2. **Ondas infinitas** (liberadas depois da 1ª camada): o mais fundo que você conseguir. O recorde fica guardado, e o Ed cresce com a profundidade.
3. **Missões da história:** de 5 a 8 ondas, cada uma com um objetivo:
   - proteger um download até terminar;
   - destruir nós da rede;
   - escoltar um programa;
   - caçar um alvo;
   - aguentar até a extração.

## 10. A quest line e os três caminhos [decidido: depois da 1ª camada, definitivo por save]

**Personagens novos no mundo do 2077 [decidido]** (os nomes são proposta):
- **Rhyme**, a fixer de Watson que dá o primeiro serviço e apresenta as três saídas;
- **Juno Takeda**, netrunner que quer montar uma equipe com você;
- **Agente Halloran**, recrutadora da Netwatch;
- **a voz do outro lado da Blackwall**, que fala com você nas camadas fundas, seja qual for o caminho.

### Solo
Você recusa os dois convites.
- **Buffs maiores:** +25% de dano e +20% de Integridade, e os ups oferecem 4 opções em vez de 3.
- **Lobo solitário:** cada onda sem levar dano dá +5% de dano até o fim do mergulho.
- Missões só suas; no fim, você atravessa a Blackwall sozinha.

### Equipe netrunner
Juno e mais dois netrunners entram com você. Cada um tem uma especialidade (dano, controle, suporte) e lança hacks sozinho.
- **Coleta automática de Ed [decidido]:** no mergulho, a equipe recolhe o Ed do chão. Fora dele (inclusive com o jogo fechado), faz serviços e rende Ed por hora. É o lado incremental.
- Seus buffs pessoais são menores. Os membros da equipe sobem de nível com Ed.

### Netwatch [decidido: um misto dos outros dois]
- **Um parceiro:** um agente da Netwatch, um aliado forte.
- **Deck próprio:** o Netdriver MK.5, de 6 slots.
- **Buffs médios:** +12% de dano e +10% de Integridade.
- **Salário por hora:** renda passiva menor que a da equipe.
- **Missões:** caçar IAs renegadas e netrunners rebeldes, inclusive os Voodoo Boys. O preço é a sua consciência, e o fim é diferente.

## 11. Visual e som [decidido: neon vetorial com brilho]

- **O ciberespaço:** um fundo escuro com grade e profundidade.
- **A netrunner:** um avatar luminoso.
- **Os ICE:** formas geométricas, cada tipo com silhueta e cor próprias.
- **Os hacks:** partículas (arcos elétricos, chamas, nuvens verdes de veneno), com um tremor de tela nos acertos fortes.
- **O som:** sintetizado como no projeto-netrunner, com uma trilha ambiente.
- **A interface:** em português.

## 12. Como vou construir

- **Separação:** a lógica do jogo (ondas, hacks, builds, inimigos, progressão) fica separada do desenho. Assim ela é testada com pytest sem tela.
- **Conteúdo editável:** hacks, ups, decks, inimigos, camadas, missões e textos ficam em arquivos YAML, para ajustar sem mexer no código.
- **Salvamento:** em JSON, com o tempo fora contado (a renda da equipe e o salário da Netwatch).
- **Medição:** um robô jogador mede o ritmo, como no incremental.

**Marcos propostos** (cada um termina jogável, testado e enviado):
1. **O mergulho:** andar, mirar, 2 hacks, 3 inimigos, ondas, ups e flatline.
2. **As builds:** as 4 builds com tags, bônus e automáticos, todos os quickhacks e um chefe.
3. **O esconderijo:** a árvore, a loja, os cyberdecks e o salvamento.
4. **As camadas:** as 5 camadas, os inimigos e os chefes, e as ondas infinitas.
5. **A quest line:** os três caminhos (a equipe e a renda, a Netwatch, o solo) e as missões.
6. **O polimento:** som, trilha, efeitos, balanceamento e o .exe.

## 13. Para você decidir

1. Os nomes dos personagens (Rhyme, Juno Takeda, Agente Halloran) estão bons?
2. Morrer perde 25% do Ed do mergulho, ou volta com tudo?
3. Começar com um deck de 2 slots está bom, ou começa com 3?
4. Os números dos três caminhos (solo +25%, Netwatch +12%, equipe com aliados e renda) estão no rumo?
5. Quer tirar ou trocar algum quickhack, cyberdeck ou inimigo das listas?
