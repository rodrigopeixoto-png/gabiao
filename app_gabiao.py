import streamlit as st
import tempfile
import ezdxf
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

# ==========================================
# MOTOR DE CÁLCULO (ENGENHARIA)
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

class MuroGabiao:
    def __init__(self, peso_especifico):
        self.gama_gabiao = peso_especifico
        self.blocos = []
        
    def adicionar_bloco(self, largura, altura, pos_x, pos_y):
        self.blocos.append({"b": largura, "h": altura, "x": pos_x, "y": pos_y})
        
    def calcular_propriedades(self):
        peso_total = 0
        momento_resistente_total = 0
        altura_total = max([b["y"] + b["h"] for b in self.blocos]) if self.blocos else 0
        
        for bloco in self.blocos:
            peso_bloco = bloco["b"] * bloco["h"] * self.gama_gabiao
            cg_x = bloco["x"] + (bloco["b"] / 2)
            peso_total += peso_bloco
            momento_resistente_total += peso_bloco * cg_x
            
        return peso_total, momento_resistente_total, altura_total

class VerificacaoEstabilidade:
    def __init__(self, terrapleno, fundacao, muro):
        self.terrapleno = terrapleno
        self.fundacao = fundacao
        self.muro = muro
        
    def calcular_seguranca(self):
        if not self.muro.blocos:
            return None
            
        peso_muro, momento_resistente, altura_muro = self.muro.calcular_propriedades()
        
        # Assume a base no y mais baixo
        base_y = min([b["y"] for b in self.muro.blocos])
        blocos_base = [b for b in self.muro.blocos if abs(b["y"] - base_y) < 0.1]
        B = max([b["x"] + b["b"] for b in blocos_base]) - min([b["x"] for b in blocos_base])
        
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
        
        return {
            "FS Tombamento": round(fs_tombamento, 2),
            "FS Deslizamento": round(fs_deslizamento, 2),
            "FS Cap. Carga": round(fs_capacidade_carga, 2),
            "Tensão Máx Base (kPa)": round(sigma_max, 2),
            "Excentricidade (m)": round(excentricidade, 3),
            "Status da Base": status_base
        }

def processar_dxf(arquivo_dxf, layer_nome, peso_gabiao):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo_dxf.getvalue())
        tmp_path = tmp.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()
    
    blocos_brutos = []
    global_min_x = float('inf')
    global_min_y = float('inf')

    for entity in msp.query(f'LWPOLYLINE[layer=="{layer_nome}"]'):
        pontos = entity.get_points('xy')
        x_coords = [p[0] for p in pontos]
        y_coords = [p[1] for p in pontos]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        blocos_brutos.append({
            "largura": max_x - min_x,
            "altura": max_y - min_y,
            "min_x": min_x,
            "min_y": min_y
        })
        
        if min_x < global_min_x: global_min_x = min_x
        if min_y < global_min_y: global_min_y = min_y

    muro = MuroGabiao(peso_especifico=peso_gabiao)
    for b in blocos_brutos:
        muro.adicionar_bloco(
            largura=b["largura"], 
            altura=b["altura"], 
            pos_x=b["min_x"] - global_min_x,
            pos_y=b["min_y"] - global_min_y
        )
    return muro

def plotar_muro(muro):
    fig, ax = plt.subplots(figsize=(6, 6))
    max_x, max_y = 0, 0
    for b in muro.blocos:
        rect = patches.Rectangle((b["x"], b["y"]), b["b"], b["h"], linewidth=1, edgecolor='black', facecolor='lightgray')
        ax.add_patch(rect)
        max_x = max(max_x, b["x"] + b["b"])
        max_y = max(max_y, b["y"] + b["h"])
        
    ax.set_xlim(-1, max_x + 1)
    ax.set_ylim(-1, max_y + 1)
    ax.set_aspect('equal')
    ax.set_xlabel("Largura (m)")
    ax.set_ylabel("Altura (m)")
    ax.set_title("Renderização da Seção (DXF)")
    ax.grid(True, linestyle='--', alpha=0.6)
    return fig

# ==========================================
# INTERFACE STREAMLIT (ESTILO GAWAC 3.1)
# ==========================================
st.set_page_config(page_title="Dimensionamento de Gabião", layout="wide")

st.title("Software de Dimensionamento de Gabião")
st.markdown("---")

# Layout principal: Entradas à esquerda, Resultados à direita
col_entrada, col_resultados = st.columns([1, 2])

with col_entrada:
    st.header("Entrada")
    
    with st.expander("Informações de projeto & Arquivo CAD", expanded=True):
        arquivo_dxf = st.file_uploader("Carregar seção DXF", type=["dxf"])
        layer_alvo = st.text_input("Layer dos Gabiões", value="GABIOES")
        
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

    with st.expander("Cargas"):
        st.info("Módulo de sobrecargas em desenvolvimento.")

with col_resultados:
    st.header("Resultados")
    btn_calcular = st.button("Calcular Resultados", type="primary")
    
    if btn_calcular:
        if arquivo_dxf is not None:
            try:
                # 1. Processamento e Instanciação
                muro_cad = processar_dxf(arquivo_dxf, layer_alvo, peso_gabiao)
                solo_terrapleno = Solo(gama_t, phi_t, q_adm, c_t)
                solo_fundacao = Solo(gama_f, phi_f, q_adm, 0)
                
                motor = VerificacaoEstabilidade(solo_terrapleno, solo_fundacao, muro_cad)
                resultados = motor.calcular_seguranca()
                
                # 2. Exibição Visual (Render)
                st.subheader("Render")
                fig = plotar_muro(muro_cad)
                st.pyplot(fig)
                
                # 3. Exibição das Métricas
                st.subheader("Verificações Físicas")
                
                # Formatação condicional para os Fatores de Segurança
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
                
                # 4. Tabela de Detalhamento
                st.write("---")
                st.dataframe(pd.DataFrame([resultados]))
                
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: Certifique-se de que o DXF possui polilinhas fechadas no layer '{layer_alvo}'. Detalhe: {e}")
        else:
            st.warning("Faça o upload de um arquivo DXF contendo a seção do muro antes de calcular.")
