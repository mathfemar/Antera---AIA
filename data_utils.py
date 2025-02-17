import os
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

def format_brazil(value: float) -> str:
    """
    Formata o número no padrão brasileiro (ex.: 1.234,56).
    """
    formatted = f"{value:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

# Diretórios para localizar arquivos
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_DADOS = os.path.join(DIRETORIO_ATUAL, 'data')

@st.cache_data
def carregar_dados():
    """
    Lê os arquivos investments.xlsx e fair_value.xlsx,
    garantindo a existência das colunas necessárias.
    """
    try:
        caminho_fair_value = os.path.join(DIRETORIO_DADOS, 'fair_value.xlsx')
        caminho_investimentos = os.path.join(DIRETORIO_DADOS, 'investimentos.xlsx')
        # Ler fair_value.xlsx
        fair_value = pd.read_excel(caminho_fair_value)
        # Ler investimentos.xlsx; se a coluna "Múltiplo" não existir, cria com valor padrão 1.0
        investimentos = pd.read_excel(caminho_investimentos)
        if 'Múltiplo' not in investimentos.columns:
            investimentos['Múltiplo'] = 1.0
        return fair_value, investimentos
    except FileNotFoundError as e:
        st.error(f"❌ Erro ao carregar os arquivos: {e}")
        return None, None
    except Exception as e:
        st.error(f"❌ Erro inesperado ao carregar os arquivos: {e}")
        return None, None

@st.cache_data
def obter_ipca():
    """
    Obtém a série histórica de IPCA via API do BCB (código 433).
    Se der erro, retorna None.
    """
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
        response = requests.get(url)
        if response.status_code == 200:
            if not response.text:
                st.error("A API do BCB retornou resposta vazia. Usando valor fixo de IPCA.")
                return None
            try:
                json_data = response.json()
            except ValueError as ve:
                st.error(f"Erro ao decodificar JSON da API do BCB: {ve}. Usando valor fixo de IPCA.")
                return None
            if not json_data:
                st.error("A API do BCB não retornou dados. Usando valor fixo de IPCA.")
                return None
            dados = pd.DataFrame(json_data)
            if 'data' not in dados.columns or 'valor' not in dados.columns:
                st.error("Resposta da API não contém os dados esperados. Usando valor fixo de IPCA.")
                return None
            dados['data'] = pd.to_datetime(dados['data'], format='%d/%m/%Y')
            dados['valor'] = pd.to_numeric(dados['valor'], errors='coerce')
            dados.dropna(subset=['valor'], inplace=True)
            dados.set_index('data', inplace=True)
            dados['variacao_decimal'] = dados['valor'] / 100
            return dados
        else:
            st.error("Erro ao acessar API do BCB. Status code: " + str(response.status_code))
            return None
    except Exception as e:
        st.error(f"Erro ao obter dados do IPCA: {e}. Usando valor fixo de IPCA.")
        return None

def calcular_ipca_acumulado(data_inicial):
    """
    Calcula o IPCA acumulado desde data_inicial até hoje.
    Se não conseguir baixar via API, usa 4,5% fixo de fallback.
    """
    df_ipca = obter_ipca()
    if df_ipca is None:
        return 0.045  # Valor fixo se a API falhar
    data_inicial = pd.to_datetime(data_inicial)
    mask = (df_ipca.index >= data_inicial)
    ipca_periodo = df_ipca[mask]
    ipca_acumulado = np.prod(1 + ipca_periodo['variacao_decimal']) - 1
    return ipca_acumulado

def corrigir_ipca(valor, data_investimento, adicional=0.0):
    """
    Corrige 'valor' pelo IPCA acumulado desde data_investimento até hoje
    e aplica 'adicional'% ao ano (ex.: IPCA+6%), proporcional ao intervalo.
    """
    data_investimento = pd.to_datetime(data_investimento)
    ipca_acum = calcular_ipca_acumulado(data_investimento)
    anos = (pd.Timestamp.now() - data_investimento).days / 365.25
    valor_corrigido_ipca = valor * (1 + ipca_acum)
    valor_final = valor_corrigido_ipca * (1 + adicional/100) ** anos
    return valor_final
