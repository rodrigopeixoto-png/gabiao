import streamlit as st
import pandas as pd
import math

# Importa as funções e classes do ficheiro que acabou de criar
from motor_cad import processar_dxf, plotar_muro, MuroGabiao 

# ... (Mantenha aqui as classes Solo e VerificacaoEstabilidade) ...

# ... (Mantenha aqui a Interface do Streamlit) ...

# 1. Função Matemática para Polígonos (Shoelace Formula)
def calcular_propriedades_poligono(pontos):
    """ Calcula a área exata e o Centro de Gravidade (Cx, Cy) de qualquer polígono fechado. """
    # Garante que o polígono fecha no ponto inicial
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
    
    # Previne divisão por zero em geometrias inválidas
    if area == 0:
        return 0, 0, 0
        
    cx = cx / (6.0 * area_signed)
    cy = cy / (6.0 * area_signed)
    
    return area, cx, cy

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
        self.blocos_poligonos = [] # Armazena as coordenadas reais dos vértices
        
    def adicionar_bloco_poligono(self, pontos):
        self.blocos_poligonos.append(pontos)
        
    def calcular_propriedades(self):
        peso_total = 0
        momento_resistente_total = 0
        
        # O ponto de giro (pé do muro) é considerado o X=0
        for pontos in self.blocos_poligonos:
            area, cx, cy = calcular_propriedades_poligono(pontos)
            peso_bloco = area * self.gama_gabiao
            
            peso_total += peso_bloco
            # O momento resistente usa a distância do CG até ao pé do muro (Cx)
            momento_resistente_total += peso_bloco * cx 
            
        # Altura total baseada no ponto mais alto e mais baixo de todos os blocos
        todos_y = [p[1] for poligono in self.blocos_poligonos for p in poligono]
        altura_total = max(todos_y) - min(todos_y) if todos_y else 0
            
        return peso_total, momento_resistente_total, altura_total

class VerificacaoEstabilidade:
    def __init__(self, terrapleno, fundacao, muro):
        self.terrapleno = terrapleno
        self.fundacao = fundacao
        self.muro = muro
        
    def calcular_seguranca(self):
        if not self.muro.blocos_poligonos:
            return None
            
        peso_muro, momento_resistente, altura_muro = self.muro.calcular_propriedades()
        
        # Encontrar a largura da base (B) projetada no solo
        # Procura o bloco mais baixo e mede a distância entre o X mínimo e o X máximo desse bloco
        todos_y = [p[1] for poligono in self.muro.blocos_poligonos for p in poligono]
        y_minimo = min(todos_y)
        blocos_base = [pol for pol in self.muro.blocos_poligonos if any(abs(p[1] - y_minimo) < 0.1 for p in pol)]
        
        x_base = [p[0] for pol in blocos_base for p in pol]
        B = max(x_base) - min(x_base)
        
        # Cálculos de Empuxo
        ka = self.terrapleno.coeficiente_empuxo_ativo()
        empuxo_ativo = 0.5 * self.terrapleno.gama * (altura_muro ** 2) * ka
        momento_tombamento = empuxo_ativo * (altura_muro / 3)
        
        # Excentricidade e Tensões
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
