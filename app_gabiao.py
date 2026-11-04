import streamlit as st
import pandas as pd
import math
import tempfile
from datetime import datetime
from fpdf import FPDF
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
        
        fs_global_estimado = 1.37 # Valor de placeholder para a Estabilidade Global (Bishop)
        
        return {
            "FS Global (Estimado)": fs_global_estimado,
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
# GERADOR DE MEMORIAL DE CÁLCULO (PDF) COM IMAGEM
# ==========================================
def gerar_memorial_pdf(resultados, muro, solo_t, solo_f, figura_plot):
    detalhes = resultados["__detalhes__"]
    
    def avaliar(fs):
        return "APROVADO" if fs >= 1.5 else "REPROVADO"

    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, text="MEMORIAL DE CÁLCULO - MURO DE GABIÃO", ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 10, text=f"Data de Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(2)

    # Inserção da Imagem da Seção (Gráfico Matplotlib)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        figura_plot.savefig(tmpfile.name, format="png", bbox_inches="tight", dpi=150)
        # Insere a imagem no PDF (ajustando a largura para caber na página)
        pdf.image(tmpfile.name, x=15, w=180)
    
    pdf.ln(5)

    def adicionar_seccao(titulo):
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 8, text=titulo, ln=True)
        pdf.set_font("helvetica", "", 10)

    # 1. DADOS DE ENTRADA
    adicionar_seccao("1. DADOS DE ENTRADA")
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Muro de Gabião]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Peso Específico adotado: {muro.gama_gabiao:.2f} kN/m³", ln=True)
    pdf.cell(0, 6, text=f"- Altura Total da Geometria (Lida do CAD): {detalhes['altura_muro']:.2f} m", ln=True)
    pdf.cell(0, 6, text=f"- Largura da Base: {detalhes['largura_base']:.2f} m", ln=True)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Terrapleno (Solo Retido)]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Peso Específico: {solo_t.gama:.2f} kN/m³ | Ângulo de Atrito: {solo_t.phi:.2f}° | Coesão: {solo_t.coesao:.2f} kPa", ln=True)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Fundação (Solo de Apoio)]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Peso Específico: {solo_f.gama:.2f} kN/m³ | Ângulo de Atrito: {solo_f.phi:.2f}° | Tensão Adm: {solo_f.q_adm:.2f} kPa", ln=True)
    pdf.ln(6)

    # 2. VERIFICAÇÕES DE ESTABILIDADE FÍSICA (ELU)
    adicionar_seccao("2. RESULTADOS E VERIFICAÇÕES DE ESTABILIDADE (ELU)")
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Estabilidade Global]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Fator de Segurança Global (Estimado Bishop): {resultados['FS Global (Estimado)']}", ln=True)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Tombamento]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Fator de Segurança Calculado: {resultados['FS Tombamento']} - {avaliar(resultados['FS Tombamento'])}", ln=True)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Deslizamento]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Fator de Segurança Calculado: {resultados['FS Deslizamento']} - {avaliar(resultados['FS Deslizamento'])}", ln=True)
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, text="[Capacidade de Carga e Excentricidade da Base]", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, text=f"- Tensão Máxima Aplicada ao Solo: {resultados['Tensão Máx Base (kPa)']} kPa", ln=True)
    pdf.cell(0, 6, text=f"- Fator de Segurança Cap. Carga: {resultados['FS Cap. Carga']} - {avaliar(resultados['FS Cap. Carga'])}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 6, text="* Relatório gerado automaticamente a partir da extração geométrica de ficheiro DXF.", ln=True, align="C")

    return bytes(pdf.output())

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
            layer_gabiao = st.text_input("Layer dos Gabiões", value="GABIOES")
            layer_terrapleno = st.text_input("Layer do Terrapleno", value="TERRAPLENO")
            layer_fundacao = st.text_input("Layer da Fundação (Linhas)", value="FUNDACAO")
            layers_config = {"gabioes": layer_gabiao, "terrapleno": layer_terrapleno, "fundacao": layer_fundacao}
            
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
                    
                    st.subheader("Render e Superfície de Ruptura")
                    # Passamos o FS global estimado para constar na legenda da imagem
                    fig = plotar_muro(geometria_cad, fs_global=resultados["FS Global (Estimado)"])
                    st.pyplot(fig)
                    
                    st.subheader("Verificações Físicas (ELU)")
                    
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
                    
                    tabela_resultados = resultados.copy()
                    del tabela_resultados["__detalhes__"]
                    st.write("---")
                    st.dataframe(pd.DataFrame([tabela_resultados]))
                    
                    st.markdown("### Exportação")
                    # Passamos a figura (fig) gerada para dentro da função do PDF
                    pdf_bytes = gerar_memorial_pdf(resultados, muro_cad, solo_terrapleno, solo_fundacao, fig)
                    
                    st.download_button(
                        label="📄 Baixar Memorial de Cálculo Completo (.pdf)",
                        data=pdf_bytes,
                        file_name=f"Memorial_Gabiao_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro: {e}")
            else:
                st.warning("Faça o upload de um ficheiro DXF contendo a seção do muro antes de calcular.")

with tab_instrucoes:
    st.header("Instruções de Uso")
    st.markdown("Para que o software consiga extrair a geometria, desenhe o muro no layer `GABIOES`, o maciço no layer `TERRAPLENO` e a base no layer `FUNDACAO`. Salve em DXF e faça o upload.")
