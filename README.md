# Blackwall Dive

Um jogo de ondas (survivor-like) com progressão incremental, no ciberespaço do Cyberpunk 2077. Você é uma netrunner freelancer de Night City. Do seu esconderijo, você mergulha camada por camada até a Blackwall: sobrevive às ondas de ICE com quickhacks, monta uma build entre as ondas e volta com Ed para ficar mais forte. O nome é provisório.

![Uma onda na rede de Night City](docs/capturas/mergulho-onda.png)

## Jogar

- **O executável (Windows e Linux):** a cada envio, o GitHub Actions gera o jogo empacotado, sem precisar de Python. Para baixar: aba **Actions** → **empacotar** → a execução mais recente → **Artifacts** → `blackwall-dive-Windows`. Descompacte e abra `blackwall-dive.exe`.
- **A partir do código:**

  ```bash
  pip install -r requirements.txt
  ```

  ```bash
  python main.py
  ```

O jogo salva sozinho (depois de cada mergulho e de cada compra) em `%APPDATA%\BlackwallDive` no Windows e em `~/.local/share/BlackwallDive` no Linux.

## Controles

| | |
|---|---|
| **Segurar o botão esquerdo** | a netrunner anda até o cursor; soltou, ela para |
| **Teclas 1 a 6** | lançam o quickhack daquele slot no ICE sob o cursor (a mira escolhe o mais perto) |
| **Botão direito** | o mesmo que a tecla 1 |
| **Tab** | mostra a build: as tags, os bônus e o ataque automático |
| **Esc** | pausa |
| **F11** | tela cheia |
| **F2** | liga e desliga o som |

## Como funciona

- **O mergulho:** cada camada tem 10 ondas de 30 a 45 segundos, com um chefe na 10ª.
  - **Integridade:** a vida. Zerou, é **flatline**: você volta com 75% do Ed do mergulho.
  - **RAM:** os hacks gastam RAM, que volta com o tempo.
  - **Ed:** cai dos ICE e é recolhido ao passar perto.
  - **Entre as ondas:** você escolhe 1 de 3 ups. Também dá para trocar as ofertas (custa Ed) ou desconectar e voltar com todo o Ed.
- **As builds:** cada up tem uma tag: Contágio, Sobrecarga, Cadeia ou Controle.
  - **Bônus de conjunto:** 2, 4 e 6 ups da mesma tag ligam um bônus cada.
  - **Ataque automático:** com 3 ups, a tag que você mais pegou liga o ataque dela, o único que ataca sozinho.
  - **O guia:** as ofertas seguintes puxam para a sua tag.
  - **O deck:** só aparecem ups das builds que os hacks do deck permitem.
  - **Sem prender:** a build deixa os hacks dela bem mais fortes, mas os outros continuam funcionando.
- **Os quickhacks:** os 15 do Cyberpunk 2077, de Short Circuit e Ping (os iniciais) a Blackwall Gateway e System Collapse. Os novos vêm ao vencer camadas, ou da loja do esconderijo.
- **Os cyberdecks:** do Militech Paraline (2 slots) ao Militech Canto MK.6 (6 slots). Cada um tem um bônus.
- **A árvore:** só números (dano, Integridade, RAM, crítico, armadura, roubo de vida...), paga com Ed. Os nós principais vão longe, então insistir sempre ajuda.
- **As camadas:** são cinco, cada uma com seu chefe:
  1. a rede de Night City (Kraken);
  2. as redes corporativas (Agente Kessler, da Netwatch);
  3. a Old Net (Liche, que se reconstrói);
  4. os arredores da Blackwall (Giant);
  5. o outro lado (a IA renegada).
- **As ondas infinitas:** liberadas depois da 1ª camada. O recorde fica guardado.

O desenho completo, com o que ainda vem (a quest line com os três caminhos, as missões da história e a renda da equipe), está em [docs/GDD.md](docs/GDD.md). As decisões e os números estão em [DECISIONS.md](DECISIONS.md).

## Para desenvolver

```
main.py               abre o jogo
blackwall/
  content.py          carrega e confere data/*.yaml
  sim/                as regras do mergulho, sem tela (testáveis)
    dive.py           ondas, ICE, chefes, dano, efeitos, ataques automáticos
    hacks.py          o que cada quickhack faz
    build.py          tags, bônus de conjunto, ofertas guiadas
    stats.py          os números da netrunner
    waves.py          o plano de cada onda
  meta/               o esconderijo: perfil, árvore, loja, decks, salvamento
  game/               a tela em pygame: neon com brilho, efeitos, sons sintetizados
data/                 o conteúdo: hacks, ups, builds, inimigos, camadas, decks, árvore e os números
tests/                pytest (as regras e a interface sem janela)
tools/
  simular.py          o robô de balanceamento
  capturas.py         fotos das telas sem abrir janela
  empacotar.py        gera o executável (PyInstaller)
```

Testes:

```bash
pip install -r requirements.txt pytest
```

```bash
python -m pytest -q tests
```

O robô de balanceamento joga carreiras inteiras e mede quantos mergulhos e minutos cada camada leva:

```bash
python tools/simular.py 3
```

Para gerar o executável localmente:

```bash
pip install -r requirements-build.txt
```

```bash
python tools/empacotar.py
```

## Créditos

- Fontes: Rajdhani e IBM Plex Mono, ambas sob a SIL Open Font License (as licenças estão em `assets/fonts/`).
- Cyberpunk 2077, Night City, Netwatch e os nomes dos quickhacks, cyberdecks e Black ICE pertencem à CD PROJEKT RED e à R. Talsorian Games. Este é um projeto de fã, sem fins comerciais.
