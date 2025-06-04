from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AnonymousUser
import re
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .forms import ClienteForm
from django.http import JsonResponse
from django.contrib.messages import get_messages
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

# Função para validar CPF
def validar_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)  # Remove caracteres não numéricos
    if len(cpf) != 11 or cpf == cpf[0] * 11:  # Impede CPFs como "111.111.111-11"
        return False

    def calcular_digito(cpf, peso):
        soma = sum(int(cpf[i]) * (peso - i) for i in range(peso - 1))
        digito = 11 - (soma % 11)
        return '0' if digito > 9 else str(digito)

    return cpf[-2:] == calcular_digito(cpf, 10) + calcular_digito(cpf, 11)

#Função para cadastrar usuario

def cadastro(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        cpf = request.POST.get('cpf')
        email = request.POST.get('email')
        senha = request.POST.get('senha')

        # Validação de campos obrigatórios
        if not (nome and cpf and email and senha):
            messages.error(request, "⚠️ <strong>Todos os campos são obrigatórios.</strong>", extra_tags='alert-danger')
            return redirect('clientes:cadastro')

        # Validação de CPF
        if not validar_cpf(cpf):
            messages.error(request, "🚨 <strong>CPF inválido.</strong> Verifique e tente novamente.", extra_tags='alert-danger')
            return redirect('clientes:cadastro')

        # Verificar se já existe CPF ou e-mail
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM usuario WHERE Cpf = %s OR Email = %s", [cpf, email])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "🚨 <strong>Este CPF ou e-mail já está cadastrado.</strong>", extra_tags='alert-danger')
                return redirect('clientes:cadastro')

        # Criptografar senha
        senha_hash = make_password(senha)

        # Inserir usuário no banco
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuario (Nome, Cpf, Email, Senha)
                VALUES (%s, %s, %s, %s)
            """, [nome, cpf, email, senha_hash])

        messages.success(request, "✅ <strong>Usuário cadastrado com sucesso!</strong> Agora você pode fazer login.", extra_tags='alert-success')
        return redirect('clientes:login')

    return render(request, 'clientes/cadastro.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        senha = request.POST.get('password')

        with connection.cursor() as cursor:
            cursor.execute("SELECT id_usuario, Senha, Nome FROM usuario WHERE Email = %s", [email])
            user_data = cursor.fetchone()

        if user_data:
            user_id, senha_hash, nome = user_data

            if check_password(senha, senha_hash):
                # Cria ou recupera um usuário Django apenas com os dados mínimos
                user, created = User.objects.get_or_create(
                    username=email,
                    defaults={'first_name': nome}
                )
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return redirect('clientes:listar_clientes')  # Redireciona após login
            else:
                messages.error(request, "🚨 Senha incorreta.", extra_tags='alert-danger')
        else:
            messages.error(request, "🚨 Usuário não encontrado.", extra_tags='alert-danger')

    return render(request, 'clientes/login.html')  # Página de login no GET ou erro

# Logout de usuário
def logout_view(request):
    logout(request)
    return redirect('clientes:login')


#Função para listar clientes

@login_required
def listar_clientes(request):
    search_query = request.GET.get('search', '')
    order_by = request.GET.get('order_by', 'nome')  # Certifique-se de que o nome do campo está correto

    # Lista de colunas permitidas para ordenação (evita SQL Injection)
    colunas_permitidas = ['id', 'nome', 'cpf_cnpj', 'endereco', 'telefone', 'celular', 'email']
    if order_by.lower() not in colunas_permitidas:
        order_by = 'nome'  # Padrão seguro

    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                f"SELECT id, nome, cpf_cnpj, endereco, telefone, celular, email FROM Cliente WHERE nome LIKE %s ORDER BY {order_by}",
                ['%' + search_query + '%']
            )
        else:
            cursor.execute(f"SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM Cliente ORDER BY {order_by}")
        
        clientes = cursor.fetchall()

    # Convertendo os resultados para um dicionário
    clientes_list = [
        {'id': c[0], 'nome': c[1], 'cpf_cnpj': c[2], 'endereco': c[3], 'telefone': c[4], 'celular': c[5], 'email': c[6]}
        for c in clientes
    ]

    return render(request, 'clientes/listar_clientes.html', {'clientes': clientes_list, 'order_by': order_by})


# Função para adicionar um novo cliente ao banco de dados usando SQL puro
@login_required
def adicionar_cliente(request):
    if request.method == 'POST':
        # Captura os dados diretamente do formulário HTML
        nome = request.POST.get('nome')
        cpf_cnpj = request.POST.get('cpf_cnpj')
        endereco = request.POST.get('endereco')
        telefone = request.POST.get('telefone', '')  # Opcional
        celular = request.POST.get('celular')
        email = request.POST.get('email')
        
        # Verificação se os campos obrigatórios foram preenchidos
        if not nome or not cpf_cnpj or not endereco or not celular or not email:
            messages.error(request, "Todos os campos obrigatórios devem ser preenchidos.")
            return render(request, 'clientes/adicionar_cliente.html')

        with connection.cursor() as cursor:
            # Verifica se já existe um cliente com esse CPF/CNPJ
            cursor.execute("SELECT COUNT(*) FROM cliente WHERE cpf_cnpj = %s", [cpf_cnpj])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "Já existe um cliente cadastrado com este CPF/CNPJ.")
            else:
                try:
                    # Insere o novo cliente no banco de dados
                    cursor.execute("""
                        INSERT INTO cliente (nome, cpf_cnpj, endereco, telefone, celular, email)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [nome, cpf_cnpj, endereco, telefone, celular, email])

                    messages.success(request, "Cliente adicionado com sucesso!")
                    return redirect('clientes:listar_clientes')
                except Exception as e:
                    messages.error(request, f"Erro ao cadastrar o cliente: {str(e)}")

    # Retorna a página de cadastro em caso de GET ou erro no POST
    return render(request, 'clientes/adicionar_cliente.html')


# Função para visualizar um cliente específico
@login_required
def visualizar_cliente(request, id_cliente):
    with connection.cursor() as cursor:
        cursor.execute("SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM cliente WHERE id_cliente = %s", [id_cliente])
        cliente = cursor.fetchone()
        
    if not cliente:
        messages.error(request, "Cliente não encontrado.")
        return redirect('clientes:listar_clientes')
    
    # Convertendo para dicionário
    cliente_dict = {
        'id_cliente': cliente[0],
        'nome': cliente[1],
        'cpf_cnpj': cliente[2],
        'endereco': cliente[3],
        'telefone': cliente[4],
        'celular': cliente[5],
        'email': cliente[6],
    }
    
    return render(request, 'clientes/visualizar_cliente.html', {'cliente': cliente_dict})

# Função para editar cliente

@login_required
def editar_cliente(request, id_cliente):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email
            FROM Cliente WHERE id_cliente = %s
        """, [id_cliente])
        cliente = cursor.fetchone()

    if not cliente:
        messages.error(request, "Cliente não encontrado.")
        return redirect('clientes:listar_clientes')

    # Criar um dicionário com os dados do cliente
    cliente_dict = {
        'id_cliente': cliente[0],
        'nome': cliente[1],
        'cpf_cnpj': cliente[2],
        'endereco': cliente[3],
        'telefone': cliente[4],
        'celular': cliente[5],
        'email': cliente[6],
    }

    if request.method == 'POST':
        form = ClienteForm(request.POST)  # Captura os dados preenchidos pelo usuário
        if form.is_valid():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE Cliente 
                        SET nome = %s, cpf_cnpj = %s, endereco = %s, telefone = %s, celular = %s, email = %s 
                        WHERE id_cliente = %s
                    """, [
                        form.cleaned_data['nome'],
                        form.cleaned_data['cpf_cnpj'],
                        form.cleaned_data['endereco'],
                        form.cleaned_data['telefone'],
                        form.cleaned_data['celular'],
                        form.cleaned_data['email'],
                        id_cliente  # Corrigido aqui
                    ])
                messages.success(request, "Cliente atualizado com sucesso!")
                return redirect('clientes:listar_clientes')  # Agora redireciona corretamente
            except Exception as e:
                messages.error(request, f"Erro ao atualizar cliente: {str(e)}")
        else:
            messages.error(request, "Erro ao salvar. Verifique os campos obrigatórios.")
    else:
        form = ClienteForm(initial=cliente_dict)  # Preenche o formulário com os dados antigos

    return render(request, 'clientes/editar_cliente.html', {'form': form, 'cliente': cliente_dict})



def validar_cpf_cnpj(valor):
    import re
    if not re.match(r'^(\d{11}|\d{14})$', valor):
        raise ValidationError("CPF/CNPJ inválido. Deve conter 11 ou 14 dígitos numéricos.")


# Função para limpar mensagem de sucesso

def limpar_mensagens(request):
    storage = get_messages(request)
    for _ in storage:
        pass  # Percorre as mensagens para limpar
    return JsonResponse({"status": "ok"})

# Função para excluir cliente

@login_required
def excluir_cliente(request, cliente_id):
    if request.method == "POST":  # Garante que a exclusão ocorre apenas via POST
        with connection.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM cliente WHERE id_cliente = %s", [cliente_id])
                messages.success(request, "Cliente excluído com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao excluir o cliente: {str(e)}")

    return redirect('clientes:listar_clientes')  # Redireciona para a listagem após excluir