# Dimensionamento de Muros de Arrimo em Gabião 🧱

Software desenvolvido em Python com interface em Streamlit para calcular e verificar a estabilidade física de muros de arrimo em gabião, inspirando-se no fluxo de trabalho do GAWAC. 

O programa lê a geometria diretamente de um ficheiro CAD (.dxf) e realiza os cálculos de engenharia.

## Funcionalidades
- **Importação de Geometria:** Leitura automática de ficheiros `.dxf`.
- **Cálculo de Empuxo:** Utilização do método de Rankine.
- **Verificações de Segurança:** 
  - Fator de Segurança ao Tombamento.
  - Fator de Segurança ao Deslizamento.
  - Capacidade de Carga (Tensão na base e excentricidade).
- **Renderização Visual:** Geração automática do perfil 2D lido do AutoCAD.

## Regras de Desenho no CAD (AutoCAD/ZWCAD/BricsCAD)
Para que o software leia a geometria corretamente, o seu desenho `.dxf` deve seguir estas regras:
1. Cada caixa do gabião deve ser desenhada como uma polilinha fechada (`LWPOLYLINE`) ou retângulo.
2. Todos os gabiões do muro devem estar desenhados num layer chamado exatamente **`GABIOES`**.
3. Guarde o ficheiro no formato DXF (qualquer versão).

## Como Instalar e Executar

1. Clone este repositório no seu computador:
```bash
git clone [https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git](https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git)
