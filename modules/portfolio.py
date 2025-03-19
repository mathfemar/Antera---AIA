import streamlit as st
import pandas as pd
import numpy as np

def init_writeoff_status():
    """
    Inicializa o status de Write-off para todas as empresas com múltiplo 0.
    Deve ser chamada logo após carregar os dados.
    """
    if 'edited_df' in st.session_state:
        for _, row in st.session_state.edited_df.iterrows():
            empresa = row["Empresa"]
            multiplo = float(row["Múltiplo"])
            
            # Se o múltiplo for 0, marca como write-off automaticamente
            if multiplo == 0:
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == empresa, "Write-off"
                ] = True
                
                # Também atualiza a variável de sessão para o checkbox
                st.session_state[f"writeoff_{empresa}"] = True
            else:
                # Garante que empresas com múltiplo > 0 não estejam marcadas como write-off
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == empresa, "Write-off"
                ] = False
                
                # Também atualiza a variável de sessão para o checkbox
                st.session_state[f"writeoff_{empresa}"] = False

def sincronizar_writeoff_com_multiplos():
    """
    Sincroniza o status de write-off com empresas que têm múltiplo zero.
    Deve ser chamada depois de carregar os dados iniciais.
    """
    if 'edited_df' in st.session_state:
        # Encontra todas as empresas com múltiplo 0
        empresas_com_multiplo_zero = st.session_state.edited_df[
            st.session_state.edited_df['Múltiplo'] == 0
        ]['Empresa'].tolist()
        
        # Marca essas empresas como write-off
        for empresa in empresas_com_multiplo_zero:
            # Atualiza o DataFrame
            st.session_state.edited_df.loc[
                st.session_state.edited_df['Empresa'] == empresa, 'Write-off'
            ] = True
            
            # Também atualiza a variável de session_state se já existir
            if f"writeoff_{empresa}" in st.session_state:
                st.session_state[f"writeoff_{empresa}"] = True

def sincronizar_multiplo_writeoff():
    """
    Assegura que a relação entre múltiplo e write-off esteja consistente.
    Deve ser chamada sempre que carregar a interface para uma empresa.
    """
    if 'select_company' in st.session_state:
        comp = st.session_state["select_company"]
        try:
            multiplo = st.session_state[f"num_{comp}"]
            
            # Se o múltiplo for zero, o write-off deve estar marcado
            if multiplo == 0:
                st.session_state[f"writeoff_{comp}"] = True
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == comp, "Write-off"
                ] = True
            # Se o múltiplo for maior que zero, o write-off não deve estar marcado
            else:
                st.session_state[f"writeoff_{comp}"] = False
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == comp, "Write-off"
                ] = False
        except:
            # Se a empresa ainda não está no sistema, não faz nada
            pass

def preparar_dados_iniciais(fair_value, investimentos):
    """
    Prepara o DataFrame inicial com os dados de investimentos e fair value.
    """
    # Tabela base
    df_empresas = investimentos[[
        'Múltiplo',
        'Empresa',
        'Valor Investido até a presente data (R$ mil)',
        'Participação do Fundo (%)',
        'Data do Primeiro Investimento'
    ]].copy()
    df_empresas.rename(columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, inplace=True)
    
    # Adicionamos "Fair Value" total (da planilha fair_value.xlsx)
    if "Fair Value" not in df_empresas.columns:
        df_empresas["Fair Value"] = np.nan
    
    # Adicionamos coluna de "Write-off" se não existir
    if "Write-off" not in df_empresas.columns:
        df_empresas["Write-off"] = False
    
    # Preenche Fair Value total do df_empresas
    for i, row in df_empresas.iterrows():
        emp = row["Empresa"]
        match = fair_value.loc[
            fair_value["Empresa"].str.upper() == emp.strip().upper()
        ]
        if not match.empty:
            df_empresas.at[i, "Fair Value"] = match.iloc[0]["Valor Primatec (R$ mil)"]
        else:
            df_empresas.at[i, "Fair Value"] = np.nan
    
    return df_empresas

def gerar_analise_crescimento(active_investments, corrigir_ipca):
    """
    Gera DataFrame com análise de crescimento para empresas ativas.
    """
    analise_crescimento = pd.DataFrame()
    
    for _, row in active_investments.iterrows():
        valor_investido = row['Valor Investido']
        valor_necessario = corrigir_ipca(
            valor_investido,
            row['Data do Primeiro Investimento'],
            adicional=6.0
        )
        fair_value_total = row["Fair Value"]
        pct_fundo = row['Participação do Fundo (%)']
        if pd.notna(fair_value_total) and pct_fundo > 0:
            fv_part = fair_value_total * (pct_fundo / 100.0)
        else:
            fv_part = np.nan
        
        multiplicador = row['Múltiplo']
        sale_value = valor_investido * multiplicador
        
        analise_crescimento = pd.concat([
            analise_crescimento,
            pd.DataFrame({
                'Empresa': [row['Empresa']],
                'Valor Investido': [valor_investido],
                'FV Part.': [fv_part],
                'IPCA+6%': [valor_necessario],
                'Participação do Fundo (%)': [pct_fundo],
                'Múltiplo': [multiplicador],
                'Sale': [sale_value],
                'Write-off': [row.get('Write-off', False)]
            })
        ])
    
    # Cálculo do Peso na Carteira
    valor_total_fv_part = analise_crescimento["FV Part."].sum()
    if valor_total_fv_part != 0:
        analise_crescimento["Peso na Carteira"] = (
            analise_crescimento["FV Part."] / valor_total_fv_part
        ) * 100
    else:
        analise_crescimento["Peso na Carteira"] = 0
    
    return analise_crescimento.round(2)
