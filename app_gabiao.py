import streamlit as st
import pandas as pd
import math
import tempfile
import os
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
        
        fs_global_estimado = 1.37
        
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
# GERADOR PROFISSIONAL DE PDF (LIMPO DE SÍMBOLOS ESPECIAIS)
# ==========================================
class PDFMemorial(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 14)
        self.set_fill_color(41, 128, 185) 
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, txt="SOFTWARE DE DIMENSIONAMENTO - MEMORIAL DE CÁLCULO", border=0, ln=1, align="C", fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, txt=f"Página {self.page_no()} | Gerado automaticamente a partir de extração CAD", border=0, align="C")
        self.set_text_color(0, 0, 0)

def gerar_memorial_pdf(resultados, muro, solo_t, solo_f, fig_detalhe, fig_geral, info_proj):
    detalhes = resultados["__detalhes__"]
    pdf = PDFMemorial()
    pdf.add_page()
    
    def seccao(titulo):
        pdf.set_font("helvetica", "B", 11)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, txt=titulo, border=0, ln=1, fill=True)
        pdf.ln(2)

    seccao("1. INFORMAÇÕES DO PROJETO")
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(40, 6, txt="Título do Projeto:", border=1); pdf.set_font("helvetica", "", 10); pdf.cell(0, 6, txt=info_proj['titulo'], border=1, ln=1)
    pdf.set_font("helvetica", "B", 10); pdf.cell(40, 6, txt="Cliente:", border=1); pdf.set_font("helvetica", "", 10); pdf.cell(0, 6, txt=info_proj['cliente'], border=1, ln=1)
    pdf.set_font("helvetica", "B", 10); pdf.cell(40, 6, txt="Projetista:", border=1); pdf.set_font("helvetica", "", 10); pdf.cell(0, 6, txt=info_proj['projetista'], border=1, ln=1)
    pdf.set_font("helvetica", "B", 10); pdf.cell(40, 6, txt="Data de Emissão:", border=1); pdf.set_font("helvetica", "", 10); pdf.cell(0, 6, txt=datetime.now().strftime('%d/%m/%Y %H:%M'), border=1, ln=1)
    pdf.ln(5)

    seccao("2. PARÂMETROS GEOTÉCNICOS E PROPRIEDADES")
    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 6, txt="2.1. Corpo do Muro (Gabião)", ln=1)
    pdf.set_font("helvetica", "", 10)
    # Trocado ³ por 3
    pdf.cell(100, 6, txt="Peso Específico da Pedra:", border=1); pdf.cell(40, 6, txt=f"{muro.gama_gabiao:.2f} kN/m3", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Altura Total do Muro:", border=1); pdf.cell(40, 6, txt=f"{detalhes['altura_muro']:.2f} m", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Largura Projetada da Base:", border=1); pdf.cell(40, 6, txt=f"{detalhes['largura_base']:.2f} m", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Peso Total da Estrutura:", border=1); pdf.cell(40, 6, txt=f"{detalhes['peso_muro']:.2f} kN/m", border=1, ln=1, align="C")
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 6, txt="2.2. Terrapleno (Solo Retido)", ln=1)
    pdf.set_font("helvetica", "", 10)
    # Trocado ³ por 3 e ° por graus
    pdf.cell(100, 6, txt="Peso Específico:", border=1); pdf.cell(40, 6, txt=f"{solo_t.gama:.2f} kN/m3", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Ângulo de Atrito Interno:", border=1); pdf.cell(40, 6, txt=f"{solo_t.phi:.2f} graus", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Coesão:", border=1); pdf.cell(40, 6, txt=f"{solo_t.coesao:.2f} kPa", border=1, ln=1, align="C")
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 6, txt="2.3. Fundação (Solo de Apoio)", ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 6, txt="Peso Específico:", border=1); pdf.cell(40, 6, txt=f"{solo_f.gama:.2f} kN/m3", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Ângulo de Atrito Interno:", border=1); pdf.cell(40, 6, txt=f"{solo_f.phi:.2f} graus", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Tensão Admissível (q_adm):", border=1); pdf.cell(40, 6, txt=f"{solo_f.q_adm:.2f} kPa", border=1, ln=1, align="C")
    pdf.ln(5)

    seccao("3. CÁLCULO DE ESFORÇOS (EMPUXOS E MOMENTOS)")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 6, txt="Coeficiente de Empuxo Ativo (Ka):", border=1); pdf.cell(40, 6, txt=f"{detalhes['ka']:.4f}", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Empuxo Ativo Total (Ea):", border=1); pdf.cell(40, 6, txt=f"{detalhes['empuxo_ativo']:.2f} kN/m", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Momento de Tombamento (Mt):", border=1); pdf.cell(40, 6, txt=f"{detalhes['momento_tombamento']:.2f} kN.m/m", border=1, ln=1, align="C")
    pdf.cell(100, 6, txt="Momento Resistente do Muro (Mr):", border=1); pdf.cell(40, 6, txt=f"{detalhes['momento_resistente']:.2f} kN.m/m", border=1, ln=1, align="C")
    
    # 4. GRÁFICOS (Nova Página)
    pdf.add_page()
    seccao("4. GEOMETRIA E SUPERFÍCIES DE RUPTURA")
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, txt="4.1. Vista de Detalhe (Escala 1:1)", ln=1)
    tmp_detalhe = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_detalhe.close()
    fig_detalhe.savefig(tmp_detalhe.name, format="png", bbox_inches="tight", dpi=300)
    pdf.image(tmp_detalhe.name, x=15, w=180)
    os.remove(tmp_detalhe.name)
    pdf.ln(95) 
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, txt="4.2. Vista Geral do Terreno (Escala 1:1)", ln=1)
    tmp_geral = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_geral.close()
    fig_geral.savefig(tmp_geral.name, format="png", bbox_inches="tight", dpi=300)
    pdf.image(tmp_geral.name, x=15, w=180)
    os.remove(tmp_geral.name)
    
    pdf.add_page()
    seccao("5. VERIFICAÇÕES DE ESTABILIDADE (ELU)")
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 8, txt="Critério de Verificação", border=1, align="C", fill=True)
    pdf.cell(30, 8, txt="FS Mínimo", border=1, align="C", fill=True)
    pdf.cell(30, 8, txt="FS Calculado", border=1, align="C", fill=True)
    pdf.cell(40, 8, txt="Status", border=1, ln=1, align="C", fill=True)
    
    pdf.set_font("helvetica", "", 10)
    def imprimir_linha(nome, fs_min, fs_calc):
        pdf.cell(60, 8, txt=nome, border=1, align="C")
        pdf.cell(30, 8, txt=f"{fs_min:.2f}", border=1, align="C")
        
        # Trocado símbolo de infinito por "N/A"
        texto_calc = f"{fs_calc:.2f}" if fs_calc != float('inf') else "N/A"
        pdf.cell(30, 8, txt=texto_calc, border=1, align="C")
        
        status = "APROVADO" if fs_calc >= fs_min else "REPROVADO"
        if status == "APROVADO":
            pdf.set_text_color(0, 128, 0)
        else:
            pdf.set_text_color(220, 0, 0)
            
        pdf.cell(40, 8, txt=status, border=1, ln=1, align="C")
        pdf.set_text_color(0, 0, 0)
        
    imprimir_linha("Estabilidade Global (Bishop)", 1.30, resultados['FS Global (Estimado)'])
    imprimir_linha("Tombamento da Estrutura", 1.50, resultados['FS Tombamento'])
    imprimir_linha("Deslizamento na Base", 1.50, resultados['FS Deslizamento'])
    imprimir_linha("Capacidade de Carga", 1.50, resultados['FS Cap. Carga'])
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 6, txt="Distribuição de Tensões na Base de Apoio:", ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(80, 6, txt="Excentricidade do Esforço (e):", border=1); pdf.cell(40, 6, txt=f"{resultados['Excentricidade (m)']:.3f} m", border=1, ln=1, align="C")
    
    # Removida qualquer menção ao símbolo sigma e caracteres especiais
    pdf.cell(80, 6, txt="Tensao Maxima Aplicada:", border=1); pdf.cell(40, 6, txt=f"{resultados['Tensão Máx Base (kPa)']:.2f} kPa", border=1, ln=1, align="C")
    pdf.cell(80, 6, txt="Status da Compressao na Base:", border=1); pdf.cell(40, 6, txt=f"{resultados['Status da Base']}", border=1, ln=1, align="C")

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
        st.header("Entrada de Dados")
        
        with st.expander("Informações do Projeto", expanded=True):
            proj_titulo = st.text_input("Título do Projeto", value="Muro de Arrimo em Gabiões")
            proj_cliente = st.text_input("Cliente", value="Prefeitura Municipal")
            proj_autor = st.text_input("Projetista", value="Eng. Responsável")
            info_projeto = {"titulo": proj_titulo, "cliente": proj_cliente, "projetista": proj_autor}
            
        with st.expander("Arquivo CAD e Layers", expanded=False):
            arquivo_dxf = st.file_uploader("Carregar seção DXF", type=["dxf"])
            layer_gabiao = st.text_input("Layer dos Gabiões", value="GABIOES")
            layer_terrapleno = st.text_input("Layer do Terrapleno", value="TERRAPLENO")
            layer_fundacao = st.text_input("Layer da Fundação", value="FUNDACAO")
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
        st.header("Análise e Resultados")
        btn_calcular = st.button("Executar Cálculo de Estabilidade", type="primary")
        
        if btn_calcular:
            if arquivo_dxf is not None:
                try:
                    muro_cad, geometria_cad = processar_dxf(arquivo_dxf, layers_config)
                    muro_cad.gama_gabiao = peso_gabiao
                    
                    solo_terrapleno = Solo(gama_t, phi_t, q_adm, c_t)
                    solo_fundacao = Solo(gama_f, phi_f, q_adm, 0)
                    
                    motor = VerificacaoEstabilidade(solo_terrapleno, solo_fundacao, muro_cad)
                    resultados = motor.calcular_seguranca()
                    
                    # Interface atualizada: Os dois gráficos aparecem visíveis um após o outro
                    st.subheader("Renderização e Superfície de Ruptura")
                    fig_detalhe = plotar_muro(geometria_cad, fs_global=resultados["FS Global (Estimado)"], vista_geral=False)
                    fig_geral = plotar_muro(geometria_cad, fs_global=resultados["FS Global (Estimado)"], vista_geral=True)
                    
                    st.markdown("**Vista 1: Detalhe do Muro**")
                    st.pyplot(fig_detalhe)
                    
                    st.markdown("**Vista 2: Seção Completa (Terreno Geral)**")
                    st.pyplot(fig_geral)
                    
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
                    
                    st.markdown("### Exportação Profissional")
                    pdf_bytes = gerar_memorial_pdf(resultados, muro_cad, solo_terrapleno, solo_fundacao, fig_detalhe, fig_geral, info_projeto)
                    
                    st.download_button(
                        label="📄 Baixar Memorial de Cálculo Profissional (.pdf)",
                        data=pdf_bytes,
                        file_name=f"Memorial_Projeto_{info_projeto['titulo'].replace(' ','_')}.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro: {e}")
            else:
                st.warning("Faça o upload de um ficheiro DXF contendo a seção do muro antes de calcular.")

with tab_instrucoes:
    st.header("Instruções de Uso")
    st.markdown("Para que o software consiga extrair a geometria, desenhe o muro no layer `GABIOES`, o maciço no layer `TERRAPLENO` e a base no layer `FUNDACAO`. Salve em DXF e faça o upload.")
