
# --- Bloco de Imports Otimizado ---
# Apenas o que é realmente usado nas suas views
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse
from django.contrib.messages import get_messages
from .forms import UsuarioForm, ClienteForm


# --- Funções de Autenticação ---

def cadastro(request):
    """
    Processa o cadastro de um novo usuário, validando os dados
    e inserindo no banco de dados com SQL puro.
    """
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            nome = form.cleaned_data['nome']
            cpf = form.cleaned_data['cpf']
            email = form.cleaned_data['email']
            senha = form.cleaned_data['senha']
            
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM usuario WHERE Cpf = %s OR Email = %s", [cpf, email])
                    if cursor.fetchone():
                        messages.error(request, 'CPF ou E-mail já cadastrado no sistema.')
                        return render(request, 'clientes/cadastro.html', {'form': form})

                    senha_hash = make_password(senha)
                    cursor.execute(
                        "INSERT INTO usuario (Nome, Cpf, Email, Senha, Status) VALUES (%s, %s, %s, %s, %s)",
                        [nome, cpf, email, senha_hash, 'A']
                    )
                
                messages.success(request, 'Conta criada com sucesso! Você já pode fazer o login.')
                return redirect('clientes:login')
            
            except Exception as e:
                messages.error(request, f'Ocorreu um erro no servidor: {e}')
                
        return render(request, 'clientes/cadastro.html', {'form': form})
    
    else:
        form = UsuarioForm()
        return render(request, 'clientes/cadastro.html', {'form': form})


def login_view(request):
    if request.method != 'POST':
        return render(request, 'clientes/login.html')

    email = request.POST.get('username')
    senha = request.POST.get('password')

    if not email or not senha:
        # Adicionando extra_tags para a mensagem de erro
        messages.error(request, 'Por favor, preencha o e-mail e a senha.', extra_tags='alert alert-danger')
        return render(request, 'clientes/login.html')

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT Id_Usuario, Nome, Senha, Status FROM usuario WHERE Email = %s", [email])
            user_data = cursor.fetchone()

            if user_data and check_password(senha, user_data[2]):
                user_id, user_nome, _, user_status = user_data

                if user_status != 'A':
                    # Adicionando extra_tags para a mensagem de aviso (amarelo)
                    messages.warning(request, 'Este usuário está inativo.', extra_tags='alert alert-warning')
                    return render(request, 'clientes/login.html')
                
                request.session['user_id'] = user_id
                request.session['user_nome'] = user_nome
                
                return redirect('clientes:listar_clientes')
            
            else:
                # Adicionando extra_tags para a mensagem de erro
                messages.error(request, 'E-mail ou senha inválidos.', extra_tags='alert alert-danger')
                return render(request, 'clientes/login.html')

    except Exception as e:
        messages.error(request, f"Ocorreu um erro no servidor: {e}", extra_tags='alert alert-danger')
        return render(request, 'clientes/login.html')

def logout_view(request):
    try:
        del request.session['user_id']
        del request.session['user_nome']
    except KeyError:
        pass
    return redirect('clientes:login')


# --- Funções de Gerenciamento de Clientes ---

def listar_clientes(request):
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.')
        return redirect('clientes:login')

    search_query = request.GET.get('search', '')
    order_by = request.GET.get('order_by', 'nome')

    colunas_permitidas = ['id_cliente', 'nome', 'cpf_cnpj', 'endereco', 'telefone', 'celular', 'email']
    if order_by.lower() not in colunas_permitidas:
        order_by = 'nome'

    try:
        with connection.cursor() as cursor:
            if search_query:
                sql_query = f"SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM Cliente WHERE nome ILIKE %s ORDER BY {order_by}"
                cursor.execute(sql_query, ['%' + search_query + '%'])
            else:
                sql_query = f"SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM Cliente ORDER BY {order_by}"
                cursor.execute(sql_query)
            
            clientes = cursor.fetchall()

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao buscar os clientes: {e}")
        clientes = []

    clientes_list = [
        {'id_cliente': c[0], 'nome': c[1], 'cpf_cnpj': c[2], 'endereco': c[3], 'telefone': c[4], 'celular': c[5], 'email': c[6]}
        for c in clientes
    ]

    contexto = {
        'clientes': clientes_list, 
        'order_by': order_by,
        'search_query': search_query,
    }
    return render(request, 'clientes/listar_clientes.html', contexto)


def adicionar_cliente(request):
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.')
        return redirect('clientes:login')

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            nome = form.cleaned_data['nome']
            cpf_cnpj = form.cleaned_data['cpf_cnpj']
            # ... (resto dos campos) ...
            try:
                # ... (lógica de inserção no banco) ...
                messages.success(request, "Cliente adicionado com sucesso!")
                return redirect('clientes:listar_clientes')
            except Exception as e:
                messages.error(request, f"Erro ao cadastrar o cliente: {e}")
        return render(request, 'clientes/adicionar_cliente.html', {'form': form})
    else:
        form = ClienteForm()
    return render(request, 'clientes/adicionar_cliente.html', {'form': form})


def visualizar_cliente(request, id_cliente):
    # ... (código com a verificação de segurança manual) ...
    pass


def editar_cliente(request, id_cliente):
    # ... (código com a verificação de segurança manual) ...
    pass


def excluir_cliente(request, cliente_id):
    # ... (código com a verificação de segurança manual) ...
    pass

# --- Funções Utilitárias ---

def limpar_mensagens(request):
    storage = get_messages(request)
    for _ in storage:
        pass
    return JsonResponse({"status": "ok"})