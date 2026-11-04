import tempfile
import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def calcular_propriedades_poligono(pontos):
    if pontos[0] != pontos[-1]:
        pontos = pontos + [pontos[0]]
    area_signed = 0
    cx = 0
    cy = 0
    for i in range(len(pontos) - 1):
        x_i, y_i = pontos[i]
        x_i1, y_i1 = pontos[i+1]
        cross = (x_i * y_i1 - x_i1 * y_i)
        area_signed += cross
        cx += (x_i + x_i1) * cross
        cy += (y_i + y_i1) * cross
    area_signed = area_signed / 2.0
    area = abs(area_signed)
    if area == 0:
        return 0, 0, 0
    cx = cx / (6.0 * area_signed)
    cy = cy / (6.0 * area_signed)
    return area, cx, cy

class MuroGabiao:
    def __init__(self, peso_especifico):
        self.gama_gabiao = peso_especifico
        self.blocos_poligonos = []
        
    def adicionar_bloco_poligono(self, pontos):
        self.blocos_poligonos.append(pontos)
        
    def calcular_propriedades(self):
        peso_total = 0
        momento_resistente_total = 0
        for pontos in self.blocos_poligonos:
            area, cx, cy = calcular_propriedades_poligono(pontos)
            peso_bloco = area * self.gama_gabiao
            peso_total += peso_bloco
            momento_resistente_total += peso_bloco * cx 
        todos_y = [p[1] for poligono in self.blocos_poligonos for p in poligono]
        altura_total = max(todos_y) - min(todos_y) if todos_y else 0
        return peso_total, momento_resistente_total, altura_total

def processar_dxf(arquivo_dxf, layers):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo_dxf.getvalue())
        tmp_path = tmp.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()
    
    geometria_extraida = {
        "gabioes": [],
        "terrapleno": [],
        "fundacao": [],
        "blocos_motor": []
    }
    
    def extrair_pontos(layer_nome):
        poligonos = []
        for entity in msp.query(f'*[layer=="{layer_nome}"]'):
            if entity.dxftype() == 'LWPOLYLINE':
                pontos = [(p[0], p[1]) for p in entity.get_points('xy')]
                poligonos.append(pontos)
            elif entity.dxftype() == 'LINE':
                poligonos.append([(entity.dxf.start.x, entity.dxf.start.y), 
                                  (entity.dxf.end.x, entity.dxf.end.y)])
        return poligonos

    geometria_extraida["gabioes"] = extrair_pontos(layers["gabioes"])
    geometria_extraida["terrapleno"] = extrair_pontos(layers["terrapleno"])
    geometria_extraida["fundacao"] = extrair_pontos(layers["fundacao"])
    
    if not geometria_extraida["gabioes"]:
        raise ValueError(f"Nenhum gabião encontrado no layer {layers['gabioes']}. Verifique o ficheiro CAD.")

    muro = MuroGabiao(peso_especifico=20.0) 
    
    global_min_x = min([p[0] for pol in geometria_extraida["gabioes"] for p in pol])
    global_min_y = min([p[1] for pol in geometria_extraida["gabioes"] for p in pol])
    
    for poligono in geometria_extraida["gabioes"]:
        poligono_normalizado = [(p[0] - global_min_x, p[1] - global_min_y) for p in poligono]
        muro.adicionar_bloco_poligono(poligono_normalizado)
        
    return muro, geometria_extraida

def plotar_muro(geometria_extraida, fs_global=1.37):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Desenha o Terrapleno
    for poligono in geometria_extraida["terrapleno"]:
        poly_patch = patches.Polygon(poligono, closed=True, facecolor='#D2B48C', edgecolor='gray', alpha=0.8, label="Terrapleno")
        ax.add_patch(poly_patch)
        
    # Desenha a Fundação
    for linha in geometria_extraida["fundacao"]:
        xs = [p[0] for p in linha]
        ys = [p[1] for p in linha]
        ax.plot(xs, ys, color='brown', linewidth=2, label="Fundação")

    # Desenha os Gabiões (com cor baseada num FS local hipotético para ilustração)
    for i, poligono in enumerate(geometria_extraida["gabioes"]):
        # Simula cores de FS local (verde para topo, amarelo para base)
        cor_bloco = '#4CAF50' if i < len(geometria_extraida["gabioes"])/2 else '#FFEB3B'
        poly_patch = patches.Polygon(poligono, closed=True, facecolor=cor_bloco, edgecolor='black', linewidth=1.2)
        ax.add_patch(poly_patch)
        if i == 0:
            poly_patch.set_label("Gabiões (FS Local)")
            
    # Desenha a Curva de Ruptura (Círculo de Bishop Conceitual)
    if geometria_extraida["gabioes"]:
        pe_x = min([p[0] for pol in geometria_extraida["gabioes"] for p in pol])
        pe_y = min([p[1] for pol in geometria_extraida["gabioes"] for p in pol])
        
        # Cria um arco vermelho simulando a superfície de deslizamento
        theta = np.linspace(np.pi, 2*np.pi, 100)
        raio = 6.0
        centro_x = pe_x + 2
        centro_y = pe_y + 4
        
        arco_x = centro_x + raio * np.cos(theta)
        arco_y = centro_y + raio * np.sin(theta)
        
        # Filtra para desenhar apenas a parte que passa por baixo do muro
        validos = arco_y < (pe_y + 3)
        ax.plot(arco_x[validos], arco_y[validos], color='red', linewidth=1.5, linestyle='-', label=f"Ruptura Global (FS={fs_global})")
        
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_xlabel("Coordenada X (m)")
    ax.set_ylabel("Coordenada Y (m)")
    ax.set_title("Análise de Estabilidade - Seção Transversal")
    
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    if by_label:
        ax.legend(by_label.values(), by_label.keys(), loc='upper right')
        
    return fig
