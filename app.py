import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from fpdf import FPDF
from PIL import Image 
import io
import re
import os

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="SMOLamp 7.3 - Gestão",
    page_icon="💡",
    layout="wide"
)

# Estilo para deixar com cara de App
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {width: 100%; border-radius: 5px; height: 3em;}
    .css-1v0mbdj.etr89bj1 {display: block;} 
</style>
""", unsafe_allow_html=True)

# 1. Imports e Instalação Silenciosa
try:
    import fpdf
    import folium
    from folium.plugins import HeatMap
except ImportError:
    os.system('pip install fpdf folium -q')
    import fpdf
    import folium
    from folium.plugins import HeatMap

# ==========================================
# 2. COORDENADAS GEOGRÁFICAS (CACHOEIRAS DE MACACU)
# ==========================================
# Mapeamento aproximado dos centros dos bairros para gerar o calor
COORDS_BAIRROS = {
    'CENTRO': [-22.4635, -42.6539],
    'JAPUIBA': [-22.5621, -42.6923],
    'JAPUÍBA': [-22.5621, -42.6923],
    'PAPUCAIA': [-22.6134, -42.7188],
    'BOCA DO MATO': [-22.4282, -42.6321],
    'VALÉRIO': [-22.4705, -42.6602],
    'VALERIO': [-22.4705, -42.6602],
    'CAMPO DO PRADO': [-22.4589, -42.6580],
    'VENEZA': [-22.6050, -42.7100],
    'RIBEIRA': [-22.6200, -42.7300],
    'MARAPORÃ': [-22.6300, -42.7400],
    'CASTÁLIA': [-22.4500, -42.6400],
    'CASTALIA': [-22.4500, -42.6400],
    'GANGURI': [-22.4800, -42.6700],
    'SÃO FRANCISCO DE ASSIS': [-22.4650, -42.6650],
    'BOA VISTA': [-22.4550, -42.6450]
}

# ==========================================
# 3. FUNÇÕES AUXILIARES
# ==========================================

def fix_text(texto):
    if not isinstance(texto, str): return str(texto)
    mapa = {'–': '-', '—': '-', '“': '"', '”': '"', '’': "'", '•': '*'}
    for k, v in mapa.items(): texto = texto.replace(k, v)
    try: return texto.encode('latin-1', 'replace').decode('latin-1')
    except: return texto

def limpar_texto_pdf(texto):
    if not isinstance(texto, str): return str(texto)
    mapa_emojis = {'📍': '>>', '⚠️': '[!]', '🚨': '[!!!]', '✅': '[OK]', '📊': '', '🤖': 'Analise:'}
    for emoji, substituto in mapa_emojis.items(): texto = texto.replace(emoji, substituto)
    return fix_text(texto)

def converter_data_hibrida(val):
    val_str = str(val).strip()
    if val_str == '' or val_str.lower() == 'nan': return pd.NaT
    try:
        numero = float(val)
        if 35000 < numero < 60000: return datetime(1899, 12, 30) + timedelta(days=numero)
    except: pass
    try: return pd.to_datetime(val, dayfirst=True)
    except: pass
    match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', val_str)
    if match:
        try: return pd.to_datetime(match.group(1), dayfirst=True)
        except: return pd.NaT
    return pd.NaT

def converter_ico_para_png_buffer(caminho_ou_buffer):
    try:
        img = Image.open(caminho_ou_buffer)
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
    except: return None

# ==========================================
# 4. INTELIGÊNCIA ROBUSTA
# ==========================================
def gerar_analise_robusta(stats):
    eficiencia = stats['eficiencia']
    entradas = stats['entradas']
    realizados = stats['realizados']
    pendentes = stats['pendentes_safra']
    chuva = stats['chuva']
    dias_uteis = stats['dias_uteis']
    bairro_top = stats.get('top_bairro_nome', 'diversas localidades')
    prev_total = stats.get('preventiva_total', 0)
    
    if eficiencia >= 1.0:
        texto = f"O período analisado demonstra uma performance operacional EXCELENTE. A equipe atingiu uma taxa de resolução de {eficiencia:.1%}, o que indica não apenas o atendimento integral da demanda recebida ({entradas} solicitações), mas também a redução proativa do passivo histórico. O sistema opera atualmente em regime de superávit técnico, demonstrando alta capacidade de resposta."
    elif eficiencia >= 0.8:
        texto = f"O cenário operacional apresenta um desempenho SÓLIDO e equilibrado. Com uma taxa de eficácia de {eficiencia:.1%}, a equipe conseguiu acompanhar o ritmo de entrada de novos pedidos, mantendo a estabilidade do sistema de iluminação pública. A resposta às {entradas} novas solicitações foi tempestiva."
    elif eficiencia >= 0.5:
        texto = f"O período inspira ATENÇÃO gerencial. A taxa de resolução de {eficiencia:.1%} revela que a capacidade de execução atual está sendo pressionada pela demanda de entrada. Foram abertos {entradas} chamados, mas apenas {realizados} foram concluídos via ordem de serviço, gerando um acúmulo de {pendentes} novas pendências."
    else:
        texto = f"O diagnóstico é CRÍTICO. Observa-se um gargalo operacional severo, com taxa de sucesso de apenas {eficiencia:.1%}. A discrepância entre o volume de solicitações ({entradas}) e a capacidade de entrega ({realizados}) está gerando um passivo insustentável a longo prazo."

    if chuva > 0:
        texto += f" Ressalta-se que a produtividade foi impactada por fatores climáticos adversos: foram registrados {chuva} dias de chuva, reduzindo a janela operacional efetiva para apenas {dias_uteis} dias úteis."
    
    if prev_total > 0:
        texto += f" Importante destacar o esforço adicional em manutenção preventiva, onde estima-se a recuperação de {prev_total} pontos de iluminação através de rondas noturnas."

    texto += f" A análise geoespacial indica que o bairro '{bairro_top}' concentrou a maior demanda do período. Recomenda-se direcionar esforços prioritários para esta localidade."
    return texto

# ==========================================
# 5. CLASSE PDF
# ==========================================
class PDFReport(FPDF):
    def set_images(self, img_brasao_path, img_sec_path, img_ico_path):
        self.img_b = img_brasao_path
        self.img_s = img_sec_path
        self.img_i = img_ico_path

    def header(self):
        if self.img_b and os.path.exists(self.img_b): self.image(self.img_b, 10, 8, 25)
        if self.img_s and os.path.exists(self.img_s): self.image(self.img_s, 175, 8, 25)
        if self.img_i and os.path.exists(self.img_i): self.image(self.img_i, 98, 8, 15)

        self.set_y(25)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 5, fix_text('PREFEITURA MUNICIPAL DE CACHOEIRAS DE MACACU'), 0, 1, 'C')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, fix_text('SECRETARIA MUNICIPAL DE OBRAS, SANEAMENTO, URBANISMO E CONSERVAÇÃO'), 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, fix_text('SMOLamp Algoritmo Versão 7.3'), 0, 1, 'C')
        self.ln(5); self.line(10, self.get_y(), 200, self.get_y()); self.ln(5)

    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(100, 100, 100)
        self.cell(0, 10, fix_text('Copyright 2026 Equipe Administrativa - Secretaria de Obras - PMCM'), 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Arial', 'B', 12); self.set_fill_color(220, 220, 220); self.set_text_color(0, 0, 0)
        self.cell(0, 8, fix_text(title), 0, 1, 'L', 1); self.ln(2)

    def top5_box(self, title, series):
        self.set_font('Arial', 'B', 10); self.cell(0, 6, fix_text(title), 0, 1, 'L'); self.set_font('Arial', '', 9)
        if len(series) > 0:
            for b, v in series.items():
                self.cell(140, 5, fix_text(str(b)[:45]), 0, 0)
                self.cell(20, 5, str(v), 0, 1, 'R')
        else: self.cell(0, 5, "Sem dados.", 0, 1)
        self.ln(3)

def gerar_pdf_executivo(stats, texto_ia):
    pdf = PDFReport(); pdf.add_page()
    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, fix_text('RELATÓRIO DE GESTÃO - ILUMINAÇÃO PÚBLICA'), 0, 1, 'C'); pdf.ln(5)
    
    pdf.section_title("1. DIAGNÓSTICO TÉCNICO DETALHADO")
    pdf.set_font('Arial', '', 10); pdf.multi_cell(0, 5, fix_text(texto_ia)); pdf.ln(5)
    
    pdf.section_title("2. BALANÇO OPERACIONAL (PERÍODO)")
    pdf.ln(2)
    pdf.set_font('Arial', 'B', 10)
    w = 47.5
    pdf.cell(w, 10, "TOTAL (Entrada)", 1, 0, 'C'); pdf.cell(w, 10, "REALIZADOS", 1, 0, 'C')
    pdf.cell(w, 10, "PENDENTES (Atual)", 1, 0, 'C'); pdf.cell(w, 10, "EFICIENCIA %", 1, 1, 'C')
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(w, 15, str(stats['entradas']), 1, 0, 'C')
    pdf.set_text_color(0, 100, 0); pdf.cell(w, 15, str(stats['realizados']), 1, 0, 'C')
    pdf.set_text_color(150, 0, 0); pdf.cell(w, 15, str(stats['pendentes_safra']), 1, 0, 'C')
    pdf.set_text_color(0, 0, 0); pdf.cell(w, 15, f"{stats['eficiencia']:.1%}", 1, 1, 'C'); pdf.ln(15)
    
    if stats['preventiva_total'] > 0:
        pdf.section_title("3. ESTIMATIVA DE MANUTENÇÃO PREVENTIVA")
        pdf.set_font('Arial', '', 10)
        txt_prev = f"• Média Informada: {stats['preventiva_media']} pontos/dia\n• TOTAL DE PONTOS RECUPERADOS (PREVENTIVA): +{stats['preventiva_total']}"
        pdf.multi_cell(0, 6, fix_text(txt_prev), 1, 'L'); pdf.ln(5)
    
    pdf.section_title("4. MAPEAMENTO POR LOCALIDADE (TOP 5)")
    y_start = pdf.get_y()
    
    pdf.set_xy(10, y_start); pdf.set_font('Arial', 'B', 9); pdf.cell(60, 6, fix_text("MAIS SOLICITAÇÕES"), 0, 1, 'L'); pdf.set_font('Arial', '', 8)
    for b, v in stats['top_total'].items(): pdf.cell(50, 5, fix_text(str(b)[:25]), 0, 0); pdf.cell(10, 5, str(v), 0, 1, 'R')
        
    pdf.set_xy(75, y_start); pdf.set_font('Arial', 'B', 9); pdf.cell(60, 6, fix_text("MAIS REALIZADOS"), 0, 1, 'L'); pdf.set_xy(75, pdf.get_y()); pdf.set_font('Arial', '', 8)
    for b, v in stats['top_feitos'].items(): pdf.set_x(75); pdf.cell(50, 5, fix_text(str(b)[:25]), 0, 0); pdf.cell(10, 5, str(v), 0, 1, 'R')

    pdf.set_xy(140, y_start); pdf.set_font('Arial', 'B', 9); pdf.cell(60, 6, fix_text("MAIS PENDENTES"), 0, 1, 'L'); pdf.set_xy(140, pdf.get_y()); pdf.set_font('Arial', '', 8)
    for b, v in stats['top_pend'].items(): pdf.set_x(140); pdf.cell(50, 5, fix_text(str(b)[:25]), 0, 0); pdf.cell(10, 5, str(v), 0, 1, 'R')
        
    pdf.ln(10); pdf.set_y(y_start + 40)
    
    pdf.section_title("5. INDICADORES VISUAIS")
    if os.path.exists('temp_chart_pie.png'): pdf.image('temp_chart_pie.png', x=15, w=90)
    if os.path.exists('temp_chart_line.png'): pdf.set_y(pdf.get_y() - 60); pdf.image('temp_chart_line.png', x=110, w=90)
    
    # Se houver mapa, avisa
    if os.path.exists('temp_map_capture.png'): # (Opcional, futuro)
        pdf.add_page(); pdf.section_title("6. MAPA DE CALOR"); pdf.image('temp_map_capture.png', x=10, w=190)

    pdf.output("Relatorio_Gestao_Consolidado.pdf")
    files.download("Relatorio_Gestao_Consolidado.pdf")

def gerar_pdf_lista_simples(df, titulo="LISTA DE SERVIÇO"):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, fix_text(titulo), 0, 1, 'C'); pdf.ln(5)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(90, 6, "LOCAL / RUA", 1); pdf.cell(30, 6, "DATA", 1); pdf.cell(40, 6, "TIPO", 1); pdf.cell(30, 6, "STATUS", 1); pdf.ln()
    pdf.set_font('Arial', '', 8)
    for _, row in df.head(500).iterrows():
        rua = fix_text(str(row.iloc[0])[:50])
        dt = row['DT_ENTRADA'].strftime('%d/%m') if pd.notnull(row['DT_ENTRADA']) else "-"
        tipo = fix_text(str(row['CATEGORIA'])[:20])
        pdf.cell(90, 6, rua, 1); pdf.cell(30, 6, dt, 1)
        pdf.cell(40, 6, tipo, 1); pdf.cell(30, 6, "PENDENTE", 1); pdf.ln()
    pdf.output("Lista_Operacional.pdf")
    files.download("Lista_Operacional.pdf")

# ==========================================
# 6. INTERFACE WEB
# ==========================================

st.title("🚀 SMOLamp 7.3 - Edição Completa (PWA)")
st.markdown("---")

# BARRA LATERAL
with st.sidebar:
    st.header("📂 Arquivo de Dados")
    uploaded_file = st.file_uploader("Arraste o Excel aqui (Rede Local)", type=['xlsx'])
    
    st.markdown("---")
    st.header("🖼️ Identidade Visual")
    tem_brasao = os.path.exists('brasao_pmcm.png')
    tem_sec = os.path.exists('sec_obras.png')
    tem_ico = os.path.exists('SMOLamp (1).ico') or os.path.exists('SMOLamp (1).png')
    
    if tem_brasao and tem_sec and tem_ico:
        st.success("✅ Logos carregadas do sistema.")
        up_brasao, up_sec, up_ico = None, None, None
    else:
        st.warning("⚠️ Logos não encontradas. Faça upload:")
        up_brasao = st.file_uploader("Brasão", type=['png', 'jpg'])
        up_sec = st.file_uploader("Logo Secretaria", type=['png', 'jpg'])
        up_ico = st.file_uploader("Ícone", type=['png', 'ico'])

# PROCESSAMENTO PRELIMINAR IMAGENS
path_brasao = "brasao_pmcm.png" if os.path.exists("brasao_pmcm.png") else None
path_sec = "sec_obras.png" if os.path.exists("sec_obras.png") else None
path_ico = "SMOLamp (1).png" if os.path.exists("SMOLamp (1).png") else ("SMOLamp (1).ico" if os.path.exists("SMOLamp (1).ico") else None)

if up_brasao:
    path_brasao = "temp_brasao.png"
    with open(path_brasao, "wb") as f: f.write(up_brasao.getbuffer())
if up_sec:
    path_sec = "temp_sec.png"
    with open(path_sec, "wb") as f: f.write(up_sec.getbuffer())
if up_ico:
    path_ico = "temp_ico.png"
    if up_ico.name.endswith('.ico'):
        try:
            img = Image.open(up_ico); img.save(path_ico, format='PNG')
        except: path_ico = None
    else:
        with open(path_ico, "wb") as f: f.write(up_ico.getbuffer())
elif path_ico and path_ico.endswith('.ico'):
    try:
        img = Image.open(path_ico); path_ico = "temp_ico_converted.png"; img.save(path_ico, format='PNG')
    except: pass

# CARREGAMENTO DO EXCEL
df = pd.DataFrame()
mapa = {}

if uploaded_file:
    try: df_raw = pd.read_excel(uploaded_file, sheet_name='Iluminação', header=None)
    except:
        try: df_raw = pd.read_excel(uploaded_file, header=None)
        except: st.error("Erro ao ler arquivo."); st.stop()

    linha_cabecalho = 0
    for i, row in df_raw.iterrows():
        txt = " ".join([str(x) for x in row.values]).upper()
        if 'RUA' in txt and ('STATUS' in txt or 'SITUACAO' in txt):
            linha_cabecalho = i; break
            
    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, sheet_name='Iluminação' if 'Iluminação' in pd.ExcelFile(uploaded_file).sheet_names else 0, header=linha_cabecalho)
    
    if len(df) > 0:
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_rua = next((c for c in df.columns if 'RUA' in c), None)
        if col_rua:
            df = df.dropna(subset=[col_rua])
            df = df[df[col_rua].astype(str).str.strip() != '']
            
            for c in df.columns:
                if 'DATA' in c and 'FEITO' in c: mapa['DATA_ENTRADA'] = c
                elif 'DATA' in c and 'REALIZADO' in c: mapa['DATA_SAIDA'] = c
                elif 'PEDIDO' in c and 'STATUS' not in c: mapa['TIPO_PEDIDO'] = c
                elif 'LOCAL' in c or 'BAIRRO' in c: mapa['LOCALIDADE'] = c
                elif 'RUA' in c: mapa['RUA'] = c
                elif 'STATUS' in c: mapa['STATUS'] = c
            
            df['DT_ENTRADA'] = df[mapa.get('DATA_ENTRADA')].apply(converter_data_hibrida)
            df['DT_SAIDA'] = df[mapa.get('DATA_SAIDA')].apply(converter_data_hibrida)
            
            def get_status(row):
                if pd.notnull(row['DT_SAIDA']): return 'FEITO'
                txt = str(row.get(mapa.get('STATUS'), '')).lower()
                saida = str(row.get(mapa.get('DATA_SAIDA'), '')).lower()
                comb = txt + " " + saida
                if 'enel' in comb or 'rede alta' in comb: return 'AGUARDANDO ENEL'
                if 'feito' in comb or 'executado' in comb: return 'FEITO'
                return 'PENDENTE'
            
            df['STATUS_FINAL'] = df.apply(get_status, axis=1)
            
            def limpar_tipo(val):
                val = str(val).lower()
                if 'braço' in val: return 'Braço'
                if 'lâmpada' in val or 'lampada' in val: return 'Lâmpada'
                if 'globo' in val: return 'Luminária'
                if 'fio' in val: return 'Fiação'
                if 'led' in val: return 'LED'
                return 'Outros'
            df['CATEGORIA'] = df[mapa.get('TIPO_PEDIDO', 'PEDIDO')].apply(limpar_tipo)

# PAINEL
if not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    hoje = datetime.now()
    with c1: d_inicio = st.date_input("Data Início", value=datetime(hoje.year, 1, 1))
    with c2: d_fim = st.date_input("Data Fim", value=hoje)
    with c3: w_chuva = st.number_input("Dias Chuva", 0, value=0)
    with c4: w_preventiva = st.number_input("Média Prev./Dia", 0, value=0)
    
    opcoes = ['TODOS'] + sorted(df[mapa['LOCALIDADE']].astype(str).unique())
    w_localidade = st.multiselect("Bairros", options=opcoes, default=['TODOS'])
    
    if st.button("PROCESSAR DADOS", type="primary"):
        df_work = df.copy()
        if 'TODOS' not in w_localidade:
            df_work = df_work[df_work[mapa['LOCALIDADE']].isin(w_localidade)]
            
        d_inicio = pd.to_datetime(d_inicio)
        d_fim = pd.to_datetime(d_fim) + timedelta(hours=23, minutes=59)
        
        mask_in = (df_work['DT_ENTRADA'] >= d_inicio) & (df_work['DT_ENTRADA'] <= d_fim)
        entradas = len(df_work[mask_in])
        mask_out = (df_work['DT_SAIDA'] >= d_inicio) & (df_work['DT_SAIDA'] <= d_fim) & (df_work['STATUS_FINAL'] == 'FEITO')
        realizados = len(df_work[mask_out])
        
        mask_pend_safra = mask_in & ((df_work['STATUS_FINAL'] != 'FEITO') | (df_work['DT_SAIDA'] > d_fim)) & (df_work['STATUS_FINAL'] != 'AGUARDANDO ENEL')
        df_pend_safra = df_work[mask_pend_safra].sort_values('DT_ENTRADA')
        pendentes_safra = len(df_pend_safra)
        
        col_local = mapa['LOCALIDADE']
        top_total = df_work[mask_in][col_local].value_counts().head(5)
        top_feitos = df_work[mask_out][col_local].value_counts().head(5)
        top_pend = df_pend_safra[col_local].value_counts().head(5)
        try: 
            dup = df_work[mask_in][df_work[mask_in].duplicated(subset=[mapa['RUA'], col_local], keep=False)]
            top_reinc = dup[col_local].value_counts().head(5)
        except: top_reinc = pd.Series()
        
        eficiencia = realizados / entradas if entradas > 0 else 0
        dias_totais = (d_fim - d_inicio).days + 1
        dias_uteis = max(1, dias_totais - w_chuva)
        media_dia = realizados / dias_uteis
        try: top_nome = top_total.index[0]
        except: top_nome = "Geral"
        preventiva_total = w_preventiva * dias_uteis
        
        stats = {
            'entradas': entradas, 'realizados': realizados, 'pendentes_safra': pendentes_safra,
            'eficiencia': eficiencia, 'top_total': top_total, 'top_reinc': top_reinc, 
            'top_pend': top_pend, 'top_feitos': top_feitos, 'top_bairro_nome': top_nome, 
            'chuva': w_chuva, 'dias_uteis': dias_uteis, 'media_dia': media_dia,
            'preventiva_media': w_preventiva, 'preventiva_total': preventiva_total
        }
        texto_ia = gerar_analise_robusta(stats)
        
        # DASHBOARD
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("TOTAL", entradas)
        k2.metric("REALIZADOS", realizados)
        k3.metric("PENDENTES", pendentes_safra, delta_color="inverse")
        k4.metric("EFICIÊNCIA", f"{eficiencia:.1%}")
        
        if preventiva_total > 0:
            st.success(f"🛠️ **Manutenção Preventiva:** +{preventiva_total} lâmpadas (Estimativa)")
            
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("O que pedem?")
            counts = df_work[mask_in]['CATEGORIA'].value_counts()
            if not counts.empty:
                fig1, ax1 = plt.subplots(figsize=(6,4))
                wedges, _, _ = ax1.pie(counts, autopct='%1.1f%%', startangle=90, colors=plt.cm.Set3.colors)
                labels_leg = [f"{l} ({c})" for l, c in zip(counts.index, counts)]
                ax1.legend(wedges, labels_leg, title="Qtd", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                st.pyplot(fig1)
                fig1.savefig('temp_chart_pie.png', bbox_inches='tight')
        
        with g2:
            st.subheader("Evolução")
            fig2, ax2 = plt.subplots(figsize=(6,4))
            if not df_work[mask_in].empty: df_work[mask_in].set_index('DT_ENTRADA').resample('W-MON').size().plot(ax=ax2, label='Entradas', color='#2196f3')
            if not df_work[mask_out].empty: df_work[mask_out].set_index('DT_SAIDA').resample('W-MON').size().plot(ax=ax2