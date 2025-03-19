import os
import json
import streamlit as st

# Diretórios para localizar arquivos
DIRETORIO_ATUAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRETORIO_DADOS = os.path.join(DIRETORIO_ATUAL, 'data')
ARQUIVO_CENARIOS = os.path.join(DIRETORIO_DADOS, 'cenarios.json')

def carregar_cenarios():
    """
    Carrega os cenários salvos do arquivo JSON.
    """
    try:
        if os.path.exists(ARQUIVO_CENARIOS):
            with open(ARQUIVO_CENARIOS, 'r') as f:
                return json.load(f)
        else:
            return {}  # Retorna dicionário vazio se o arquivo não existir
    except Exception as e:
        st.error(f"Erro ao carregar cenários: {e}")
        return {}

def salvar_cenarios(cenarios):
    """
    Salva os cenários em um arquivo JSON.
    """
    try:
        # Certifique-se que o diretório existe
        diretorio = os.path.dirname(ARQUIVO_CENARIOS)
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
            
        with open(ARQUIVO_CENARIOS, 'w') as f:
            json.dump(cenarios, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar cenários: {e}")
        return False

def salvar_cenario_atual():
    """
    Salva o cenário atual com o nome fornecido pelo usuário.
    """
    nome_cenario = st.session_state.novo_cenario
    if not nome_cenario or nome_cenario.strip() == "":
        st.warning("Por favor, insira um nome para o cenário.")
        return
    
    # Obtém os múltiplos e status de write-off atuais
    dados_empresas = {}
    for _, row in st.session_state.edited_df.iterrows():
        empresa = row["Empresa"]
        dados_empresas[empresa] = {
            "Múltiplo": float(row["Múltiplo"]),
            "Write-off": bool(row.get("Write-off", False))
        }
    
    # Carrega cenários existentes e adiciona/atualiza o novo
    cenarios = carregar_cenarios()
    cenarios[nome_cenario] = dados_empresas
    
    # Limita a 5 cenários
    if len(cenarios) > 5:
        # Remove o mais antigo
        oldest_key = list(cenarios.keys())[0]
        cenarios.pop(oldest_key)
    
    # Salva o arquivo atualizado
    if salvar_cenarios(cenarios):
        st.success(f"Cenário '{nome_cenario}' salvo com sucesso!")
        # Atualiza a lista de seleção
        st.session_state.cenarios_disponiveis = list(carregar_cenarios().keys())
        # Limpa o campo de texto
        st.session_state.novo_cenario = ""
    else:
        st.error("Erro ao salvar o cenário.")

def aplicar_cenario():
    """
    Aplica o cenário selecionado aos dados atuais.
    """
    nome_cenario = st.session_state.cenario_selecionado
    cenarios = carregar_cenarios()
    
    if nome_cenario in cenarios:
        dados_empresas = cenarios[nome_cenario]
        
        # Aplica os múltiplos e status de write-off ao dataframe
        for empresa, dados in dados_empresas.items():
            if empresa in st.session_state.edited_df["Empresa"].values:
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == empresa, "Múltiplo"
                ] = dados.get("Múltiplo", 0.0)
                
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["Empresa"] == empresa, "Write-off"
                ] = dados.get("Write-off", False)
                
                # Atualiza os valores da interface
                if f"writeoff_{empresa}" in st.session_state:
                    st.session_state[f"writeoff_{empresa}"] = dados.get("Write-off", False)
                if f"num_{empresa}" in st.session_state:
                    st.session_state[f"num_{empresa}"] = dados.get("Múltiplo", 0.0)
                if f"slider_{empresa}" in st.session_state:
                    st.session_state[f"slider_{empresa}"] = dados.get("Múltiplo", 0.0)
                
        st.success(f"Cenário '{nome_cenario}' aplicado com sucesso!")
    else:
        st.error(f"Cenário '{nome_cenario}' não encontrado.")

def excluir_cenario():
    """
    Exclui o cenário selecionado.
    """
    nome_cenario = st.session_state.cenario_selecionado
    cenarios = carregar_cenarios()
    
    if nome_cenario in cenarios:
        cenarios.pop(nome_cenario)
        if salvar_cenarios(cenarios):
            st.success(f"Cenário '{nome_cenario}' excluído com sucesso!")
            # Atualiza a lista de seleção
            st.session_state.cenarios_disponiveis = list(carregar_cenarios().keys())
            # Limpa a seleção
            if st.session_state.cenarios_disponiveis:
                st.session_state.cenario_selecionado = st.session_state.cenarios_disponiveis[0]
            else:
                st.session_state.cenario_selecionado = ""
        else:
            st.error("Erro ao excluir o cenário.")
    else:
        st.error(f"Cenário '{nome_cenario}' não encontrado.")

def inicializar_session_state_cenarios():
    """
    Inicializa variáveis da sessão para cenários.
    """
    if 'cenarios_disponiveis' not in st.session_state:
        st.session_state.cenarios_disponiveis = list(carregar_cenarios().keys())
    if 'cenario_selecionado' not in st.session_state and st.session_state.cenarios_disponiveis:
        st.session_state.cenario_selecionado = st.session_state.cenarios_disponiveis[0] if st.session_state.cenarios_disponiveis else ""
    if 'novo_cenario' not in st.session_state:
        st.session_state.novo_cenario = ""
