import streamlit as st
import pandas as pd
import math
from datetime import datetime
from motor_cad import processar_dxf, plotar_muro, MuroGabiao

# ==========================================
# CLASSES DE ENGENHARIA E CÁLCULO
# ==========================================
class Solo:
    def __init__(self, peso_especifico, angulo_atrito, tensao_admissivel, coesao=0):
        self.gama = peso_especifico
        self.phi = angulo_atrito
        self.coesao = coesao
        self.q_adm = tensao_admissivel
        
    def coeficiente_empuxo_ativo(self):
        rad = math.radians(45 - (self.phi / 2))
        return (math.tan(rad)) ** 2

class VerificacaoEstabilidade:
    def __init__(self, terrapleno, fundacao, muro):
        self.terrapleno = terrapleno
        self.fundacao = fundacao
        self.muro = muro
        
    def calcular_seguranca(self):
        if not self.muro.blocos_poligonos:
            return None
            
        peso_muro, momento_resistente, altura_muro = self.muro.calcular_propriedades()
        
        todos_y = [p[1] for poligono in self.muro.blocos_poligonos for p in poligono]
        y_minimo = min(todos_y)
        blocos_base = [pol for pol in self.muro.blocos_poligonos if any(abs(p[1] - y_minimo) < 0.1 for p in pol)]
        
        if blocos_base:
            x_base = [p[0] for pol in blocos_base for p in pol]
            B = max(x_base) - min(x_base)
        else:
            B = 1.0 
        
        ka = self.terrapleno.coeficiente_empuxo_ativo()
        empuxo_ativo = 0.5 * self.terrapleno.gama * (altura_muro ** 2) * ka
        momento_tombamento = empuxo_ativo * (altura_muro / 3)
        
        xR = (momento_resistente - momento_tombamento) / peso_muro if peso_muro > 0 else 0
        excentricidade = (B / 2) - xR
        
        if excentricidade <= (B / 6):
            sigma_max = (peso_muro / B) * (1 + (6 * excentricidade / B))
            status_base = "Compressão Total"
        else:
            sigma_max = (2 * peso_muro) / (3 * xR) if xR > 0 else float('inf')
            status_base = "Base Tracionada"
            
        fs_tombamento = momento_resistente / momento_tombamento if momento_tombamento > 0 else float('inf')
        fs_deslizamento = (peso_muro * math.tan(math.radians(self.fundacao.phi * 0.67))) / empuxo_ativo if empuxo_ativo > 0 else float('inf')
        fs_capacidade_carga = self.fundacao.q_adm / sigma_max if sigma_max > 0 else float('inf')
        
        # Retornamos também os dados intermediários para o Memorial de Cálculo
        return {
            "FS Tombamento": round(fs_tombamento, 2),
            "FS Deslizamento": round(fs_deslizamento, 2),
            "FS Cap. Carga": round(fs_capacidade_carga, 2),
            "Tensão Máx Base (kPa)": round(sigma_max, 2),
            "Excentricidade (m)": round(excentricidade, 3),
            "Status da Base": status_base,
            "__detalhes__": {
                "altura_muro": altura_muro,
                "peso_muro": peso_muro,
                "largura_base": B,
                "ka": ka,
                "empuxo_ativo": empuxo_ativo,
                "momento_tombamento": momento_tombamento,
                "momento_resistente": momento_resistente
            }
        }

# ==========================================
# GERADOR DE MEMORIAL DE CÁLCULO
# ==========================================
def gerar_memorial(resultados, muro, solo_t, solo_f):
    detalhes = resultados["__detalhes__"]
    
    def avaliar(fs):
        return "APROVADO" if fs >= 1.5 else "REPROVADO"

    memorial = f"""=========================================================
             MEMORIAL DE CÁLCULO - MURO DE GABIÃO
=========================================================
Data de Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}

1. DADOS DE ENTRADA
---------------------------------------------------------
[Muro de Gabião]
- Peso Específico adotado: {muro.gama_gabiao:.2f} kN/m³
- Altura Total da Geometria (Lida do CAD): {detalhes['altura_muro']:.2f} m
- Largura da Base: {detalhes['largura_base']:.2f} m
- Peso Total do Muro: {detalhes['peso_muro']:.2f} kN/m

[Terrapleno (Solo Retido)]
- Peso Específico: {solo_t.gama:.2f} kN/m³
- Ângulo de Atrito: {solo_t.phi:.2f}°
- Coesão: {solo_t.coesao:.2f} kPa

[Fundação (Solo de Apoio)]
- Peso Específico: {solo_f.gama:.2f} kN/m³
- Ângulo de Atrito: {solo_f.phi:.2f}°
- Tensão Admissível Informada: {solo_f.q_adm:.2f} kPa

2. CÁLCULO DE FORÇAS E MOMENTOS
---------------------------------------------------------
- Coeficiente de Empuxo Ativo (Ka): {detalhes['ka']:.4f}
- Empuxo Ativo Total (Ea): {detalhes['empuxo_ativo']:.2f} kN/m
- Momento de Tombamento (Mt): {detalhes['momento_tombamento']:.2f} kN.m/m
- Momento Resistente (Mr): {detalhes['momento_resistente']:.2f} kN.m/m

3. VERIFICAÇÕES DE ESTABILIDADE FÍSICA
---------------------------------------------------------
[Tombamento]
- Fator de Segurança Calculado: {resultados['FS Tombamento']}
- Status: {avaliar(resultados['FS Tombamento'])} (Mínimo exigido: 1.50)

[Deslizamento]
- Fator de Segurança Calculado: {resultados['FS Deslizamento']}
- Status: {avaliar(resultados['FS Deslizamento'])} (Mínimo exigido: 1.50)

[Capacidade de Carga e Excentricidade da Base]
- Excentricidade (e): {resultados['Excentricidade (m)']} m
- Status da Distribuição na Base: {resultados['Status da Base']}
- Tensão Máxima Aplicada ao Solo: {resultados['Tensão Máx Base (kPa)']} kPa
- Fator de Segurança Cap. Carga: {resultados['FS Cap. Carga']}
- Status: {avaliar(resultados['FS Cap. Carga'])} (Mínimo exigido: 1.50)

=========================================================
* Relatório gerado automaticamente a partir da extração 
geométrica de ficheiro DXF.
========================================================="""
    return memorial

# ==========================================
# INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Dimensionamento de Gabião", layout="wide")

st.title("Software de Dimensionamento de Gabião")
st.markdown("---")

tab_calculadora, tab_instrucoes = st.tabs(["🧮 Calculadora", "📖 Instruções de Uso"])

with tab_calculadora:
    col_entrada, col_resultados = st.columns([1, 2])

    with col_entrada:
        st.header("Entrada")
        
        with st.expander("Informações de projeto & Arquivo CAD", expanded=True):
            arquivo_dxf = st.file_uploader("Carregar seção DXF", type=["dxf"])
            
            st.markdown("**Configuração de Layers do CAD:**")
            layer_gabiao = st.text_input("Layer dos Gabiões", value="GABIOES")
            layer_terrapleno = st.text_input("Layer do Terrapleno", value="TERRAPLENO")
            layer_fundacao = st.text_input("Layer da Fundação (Linhas)", value="FUNDACAO")
            
            layers_config = {
                "gabioes": layer_gabiao,
                "terrapleno": layer_terrapleno,
                "fundacao": layer_fundacao
            }
            
        with st.expander("Muro (Produto)"):
            peso_gabiao = st.number_input("Peso Específico do Gabião (kN/m³)", value=20.0, step=1.0)
            
        with st.expander("Terrapleno (Solo Retido)"):
            gama_t = st.number_input("Peso Específico (kN/m³) - Terrapleno", value=18.0, step=0.5)
            phi_t = st.number_input("Ângulo de Atrito (°) - Terrapleno", value=30.0, step=1.0)
            c_t = st.number_input("Coesão (kPa) - Terrapleno", value=0.0, step=1.0)
            
        with st.expander("Fundação (Solo de Apoio)"):
            gama_f = st.number_input("Peso Específico (kN/m³) - Fundação", value=19.0, step=0.5)
            phi_f = st.number_input("Ângulo de Atrito (°) - Fundação", value=28.0, step=1.0)
            q_adm = st.number_input("Tensão Admissível (kPa)", value=200.0, step=10.0)

    with col_resultados:
        st.header("Resultados")
        btn_calcular = st.button("Calcular Resultados", type="primary")
        
        if btn_calcular:
            if arquivo_dxf is not None:
                try:
                    muro_cad, geometria_cad = processar_dxf(arquivo_dxf, layers_config)
                    muro_cad.gama_gabiao = peso_gabiao
                    
                    solo_terrapleno = Solo(gama_t, phi_t, q_adm, c_t)
                    solo_fundacao = Solo(gama_f, phi_f, q_adm, 0)
                    
                    motor = VerificacaoEstabilidade(solo_terrapleno, solo_fundacao, muro_cad)
                    resultados = motor.calcular_seguranca()
                    
                    st.subheader("Render")
                    fig = plotar_muro(geometria_cad)
                    st.pyplot(fig)
                    
                    st.subheader("Verificações Físicas")
                    
                    metrica_tomb, metrica_desl, metrica_cap = st.columns(3)
                    
                    def cor_status(fs):
                        return "normal" if fs >= 1.5 else "inverse"
                        
                    metrica_tomb.metric("FS Tombamento (≥1.5)", resultados["FS Tombamento"], 
                                        delta="OK" if resultados["FS Tombamento"] >= 1.5 else "INSEGURO", 
                                        delta_color=cor_status(resultados["FS Tombamento"]))
                    
                    metrica_desl.metric("FS Deslizamento (≥1.5)", resultados["FS Deslizamento"], 
                                        delta="OK" if resultados["FS Deslizamento"] >= 1.5 else "INSEGURO", 
                                        delta_color=cor_status(resultados["FS Deslizamento"]))
                                        
                    metrica_cap.metric("FS Cap. Carga (≥1.5)", resultados["FS Cap. Carga"], 
                                       delta="OK" if resultados["FS Cap. Carga"] >= 1.5 else "INSEGURO", 
                                       delta_color=cor_status(resultados["FS Cap. Carga"]))
                    
                    # Removemos os dados intermediários antes de exibir na tabela
                    tabela_resultados = resultados.copy()
                    del tabela_resultados["__detalhes__"]
                    
                    st.write("---")
                    st.dataframe(pd.DataFrame([tabela_resultados]))
                    
                    # ----------------------------------------------------
                    # BOTÃO DE EXPORTAÇÃO DO MEMORIAL
                    # ----------------------------------------------------
                    st.markdown("### Exportação")
                    texto_memorial = gerar_memorial(resultados, muro_cad, solo_terrapleno, solo_fundacao)
                    
                    st.download_button(
                        label="📄 Baixar Memorial de Cálculo (.txt)",
                        data=texto_memorial,
                        file_name=f"Memorial_Gabiao_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro: {e}")
            else:
                st.warning("Faça o upload de um ficheiro DXF contendo a seção do muro antes de calcular.")

with tab_instrucoes:
    st.header("Como preparar o desenho no CAD")
    
    st.markdown("""
    Para que o software consiga extrair a geometria perfeitamente e calcular os volumes, centros de gravidade e áreas, o seu ficheiro **.dxf** deve obedecer a três regras simples de desenho:

    ### 1. O Muro de Gabião
    * **O que desenhar:** Cada bloco (caixa) do gabião deve ser desenhado como uma **polilinha fechada** (`LWPOLYLINE`) ou retângulo.
    * **Onde colocar:** Todos os blocos devem estar obrigatoriamente num layer chamado **`GABIOES`**.
    * **Inclinação (Tilt):** Pode desenhar o muro a prumo ou com qualquer inclinação. O software calculará o centro de massa exato do polígono.

    ### 2. O Maciço / Terrapleno
    * **O que desenhar:** Desenhe o contorno completo do solo que está a ser arrimado utilizando uma **polilinha fechada**. *Não utilize "hatch" (hachuras).*
    * **Onde colocar:** Esta polilinha deve estar no layer **`TERRAPLENO`**.

    ### 3. A Fundação / Terreno de Apoio
    * **O que desenhar:** Desenhe as linhas que representam o solo onde o muro está apoiado. Podem ser linhas soltas (`LINE`) ou uma polilinha aberta.
    * **Onde colocar:** Estas linhas devem estar no layer **`FUNDACAO`**.

    ---
    
    ### ⚙️ Executando o Cálculo
    1. Guarde o seu desenho no AutoCAD/ZWCAD/BricsCAD no formato **DXF** (qualquer versão serve).
    2. Na aba **Calculadora**, faça o upload do ficheiro.
    3. Preencha as propriedades físicas do Solo e do Gabião e clique em **Calcular Resultados**.
    4. Um botão de **Download** aparecerá no final da página com o seu Memorial Descritivo completo.
    """)
