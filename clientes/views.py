
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, transaction
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse
from django.contrib.messages import get_messages
from .forms import UsuarioForm, ClienteForm, PedidoForm
from django.core.paginator import Paginator
from decimal import Decimal

def home_view(request):
    if 'user_id' not in request.session:
        # A mensagem de aviso aqui precisa das extra_tags para ter cor
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.', extra_tags='alert alert-warning')
        return redirect('clientes:login')

    user_id = request.session.get('user_id')
    pedidos_recentes = []
    user_status = None
    
    try:
        with connection.cursor() as cursor:
            # Busca o status do usuário logado (para o botão de 'Cadastrar Colaborador')
            cursor.execute("SELECT Status FROM usuario WHERE Id_Usuario = %s", [user_id])
            result = cursor.fetchone()
            if result:
                user_status = result[0]

            # CORREÇÃO PRINCIPAL: Busca os 10 últimos pedidos que NÃO estão Concluídos ou Cancelados
            cursor.execute("""
                SELECT p.Id_Pedido, c.Nome, p.Status_pedido, p.Vlr_Total_pedido 
                FROM Pedido p
                JOIN Cliente c ON p.Id_Cliente = c.id_cliente
                WHERE p.Status_pedido NOT IN ('Concluído', 'Cancelado', 'Entregue')
                ORDER BY p.Dt_Pedido DESC, p.Id_Pedido DESC 
                LIMIT 10
            """)
            pedidos_recentes = cursor.fetchall()
            
    except Exception as e:
        messages.error(request, f"Erro ao carregar o painel: {e}", extra_tags='alert alert-danger')
        
    contexto = {
        'pedidos': pedidos_recentes,
        'user_status': user_status
    }
    return render(request, 'clientes/home.html', contexto)

def novo_pedido_view(request):
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.')
        return redirect('clientes:login')

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_cliente, nome FROM cliente ORDER BY nome")
            lista_clientes = cursor.fetchall()
    except Exception as e:
        messages.error(request, f"Erro ao carregar lista de clientes: {e}")
        lista_clientes = []

    if request.method == 'POST':
        form = PedidoForm(request.POST, clientes=lista_clientes)
        
        if form.is_valid():
            id_novo_pedido = None
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # Pega dados validados
                        cliente_id = form.cleaned_data['cliente']
                        data_pedido = form.cleaned_data['data_pedido']
                        
                        # Pega dados dos itens
                        descricoes = request.POST.getlist('item_descricao')
                        materiais = request.POST.getlist('item_custo_material')
                        maos_de_obra = request.POST.getlist('item_mao_de_obra')
                        quantidades = request.POST.getlist('item_quantidade')

                        # Lógica de cálculo...
                        total_pedido, total_material, total_mao_de_obra = 0, 0, 0
                        for i in range(len(descricoes)):
                            mat = float(materiais[i].replace('.', '').replace(',', '.'))
                            mo = float(maos_de_obra[i].replace('.', '').replace(',', '.'))
                            qtd = int(quantidades[i])
                            total_pedido += (mat + mo) * qtd
                            total_material += mat * qtd
                            total_mao_de_obra += mo * qtd

                        # Insere o Pedido
                        cursor.execute(
                            "INSERT INTO Pedido (Id_Cliente, Dt_Pedido, Status_pedido, Vlr_Total_pedido, Vlr_Material, Vlr_mao_obra) VALUES (%s, %s, %s, %s, %s, %s) RETURNING Id_Pedido",
                            [cliente_id, data_pedido, 'Em Aberto', total_pedido, total_material, total_mao_de_obra]
                        )
                        resultado_insert = cursor.fetchone()
                        if not resultado_insert:
                            raise Exception("Falha ao criar o pedido principal no banco de dados.")
                        
                        id_novo_pedido = resultado_insert[0]

                        # Insere os itens
                        for i in range(len(descricoes)):
                            valor_unitario = float(materiais[i].replace('.', '').replace(',', '.'))
                            cursor.execute("INSERT INTO Produto (Nome, Descricao, Preco) VALUES (%s, %s, %s) RETURNING Id_Produto", [descricoes[i], descricoes[i], valor_unitario])
                            id_novo_produto = cursor.fetchone()[0]
                            
                            subtotal = (valor_unitario + float(maos_de_obra[i].replace(',', '.'))) * int(quantidades[i])
                            cursor.execute("INSERT INTO Pedido_Produto (Id_Pedido, Id_Produto, Qtde, Vlr_Total_Produto) VALUES (%s, %s, %s, %s)", [id_novo_pedido, id_novo_produto, quantidades[i], subtotal])

                # Se o bloco 'try' foi concluído, a transação é salva.
                messages.success(request, "Pedido criado com sucesso!", extra_tags='alert alert-success')
                return redirect('clientes:detalhes_pedido', id_pedido=id_novo_pedido)

            except Exception as e:
                # Se qualquer erro acontecer, a transação é desfeita.
                messages.error(request, f"Ocorreu um erro ao salvar o pedido: {e}", extra_tags='alert alert-danger')
        
    else: # GET
        form = PedidoForm(clientes=lista_clientes)

    # Este return é usado para o GET e para o POST que falhou em qualquer etapa
    return render(request, 'clientes/novo_pedido.html', {'form': form})

def editar_pedido_view(request, id_pedido):
    """
    Carrega os dados de um pedido para edição e processa a sua atualização.
    VERSÃO FINAL CORRIGIDA.
    """
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.', extra_tags='alert alert-warning')
        return redirect('clientes:login')

    # Busca a lista de clientes para popular o dropdown
    with connection.cursor() as cursor:
        cursor.execute("SELECT id_cliente, nome FROM cliente ORDER BY nome")
        lista_clientes = cursor.fetchall()

    # Se o formulário for enviado (método POST)
    if request.method == 'POST':
        form = PedidoForm(request.POST, clientes=lista_clientes)
        
        if form.is_valid():
            cliente_id = form.cleaned_data['cliente']
            data_pedido = form.cleaned_data['data_pedido']
            prazo_entrega = form.cleaned_data['prazo_entrega']
            observacao = form.cleaned_data['observacao']
            novo_status = request.POST.get('status_pedido')
            
            descricoes = request.POST.getlist('item_descricao')
            materiais = request.POST.getlist('item_custo_material')
            maos_de_obra = request.POST.getlist('item_mao_de_obra')
            quantidades = request.POST.getlist('item_quantidade')

            # ==========================================================
            #     PASSO 1: CALCULAR OS NOVOS TOTAIS PRIMEIRO
            #     (Esta é a parte que estava em falta e causava o erro)
            # ==========================================================
            total_pedido = 0
            total_material = 0
            total_mao_de_obra = 0
            for i in range(len(descricoes)):
                mat = float(materiais[i].replace('.', '').replace(',', '.'))
                mo = float(maos_de_obra[i].replace('.', '').replace(',', '.'))
                qtd = int(quantidades[i])
                total_pedido += (mat + mo) * qtd
                total_material += mat * qtd
                total_mao_de_obra += mo * qtd
            # ==========================================================
            
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # PASSO 2: ATUALIZA O PEDIDO PRINCIPAL (Agora as variáveis de total existem)
                        cursor.execute(
                            """
                            UPDATE Pedido 
                            SET Id_Cliente=%s, Dt_Pedido=%s, Prazo_Entrega=%s, Status_pedido=%s, 
                                Vlr_Total_pedido=%s, Vlr_Material=%s, Vlr_mao_obra=%s, Observacao=%s
                            WHERE Id_Pedido=%s
                            """,
                            [cliente_id, data_pedido, prazo_entrega, novo_status, 
                             total_pedido, total_material, total_mao_de_obra, observacao, 
                             id_pedido]
                        )

                        # PASSO 3: APAGA OS ITENS ANTIGOS
                        cursor.execute("DELETE FROM Pedido_Produto WHERE Id_Pedido = %s", [id_pedido])

                        # PASSO 4: RE-INSERE OS ITENS ATUALIZADOS
                        for i in range(len(descricoes)):
                            valor_unitario = float(materiais[i].replace('.', '').replace(',', '.'))
                            cursor.execute("INSERT INTO Produto (Nome, Descricao, Preco) VALUES (%s, %s, %s) RETURNING Id_Produto", [descricoes[i], descricoes[i], valor_unitario])
                            id_novo_produto = cursor.fetchone()[0]
                            
                            subtotal = (valor_unitario + float(maos_de_obra[i].replace('.', '').replace(',', '.'))) * int(quantidades[i])
                            cursor.execute("INSERT INTO Pedido_Produto (Id_Pedido, Id_Produto, Qtde, Vlr_Total_Produto) VALUES (%s, %s, %s, %s)", [id_pedido, id_novo_produto, quantidades[i], subtotal])
                
                messages.success(request, "Pedido atualizado com sucesso!", extra_tags='alert alert-success')
                return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

            except Exception as e:
                messages.error(request, f"Ocorreu um erro ao atualizar o pedido: {e}", extra_tags='alert alert-danger')
    
    # Se a requisição for GET ou o formulário POST for inválido
    try:
        with connection.cursor() as cursor:
            # Busca os dados atuais para preencher o formulário na primeira vez que a página carrega
            cursor.execute("SELECT Id_Cliente, Dt_Pedido, Prazo_Entrega, Status_pedido, Observacao FROM Pedido WHERE Id_Pedido = %s", [id_pedido])
            pedido_data = cursor.fetchone()
            
            if not pedido_data:
                messages.error(request, "Pedido não encontrado.")
                return redirect('clientes:home')
            
            cursor.execute("""
                SELECT p.Nome, p.Preco, pp.Qtde, (pe.Vlr_mao_obra / NULLIF((SELECT SUM(Qtde) FROM Pedido_Produto WHERE Id_Pedido=%s), 0)) as M_O_Item
                FROM Pedido_Produto pp
                JOIN Produto p ON pp.Id_Produto = p.Id_Produto
                JOIN Pedido pe ON pp.Id_Pedido = pe.Id_Pedido
                WHERE pp.Id_Pedido = %s
            """, [id_pedido, id_pedido])
            itens_atuais = cursor.fetchall()
            
    except Exception as e:
        messages.error(request, f"Não foi possível carregar o pedido para edição: {e}", extra_tags='alert alert-danger')
        return redirect('clientes:home')

    # Prepara os dados para preencher o formulário
    # Se for um POST inválido, o 'form' com os erros já existe. Se for GET, criamos um novo.
    if request.method != 'POST':
        initial_data = {
            'cliente': pedido_data[0], 'data_pedido': pedido_data[1],
            'prazo_entrega': pedido_data[2], 'observacao': pedido_data[4]
        }
        form = PedidoForm(initial=initial_data, clientes=lista_clientes)
    
    contexto = {
        'form': form, 'pedido_id': id_pedido,
        'itens': itens_atuais, 'status_atual': pedido_data[3]
    }
    return render(request, 'clientes/editar_pedido.html', contexto)
        
def atualizar_status_pedido(request, id_pedido):
    # Segurança: só permite a alteração via método POST
    if request.method != 'POST':
        return redirect('clientes:home')

    # Segurança: verifica se o usuário está logado
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para executar esta ação.')
        return redirect('clientes:login')

    novo_status = request.POST.get('novo_status')
    if not novo_status:
        messages.error(request, 'Nenhum status foi selecionado.', extra_tags='alert alert-danger')
        return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Pedido SET Status_pedido = %s WHERE Id_Pedido = %s",
                [novo_status, id_pedido]
            )
        messages.success(request, "Status do pedido atualizado com sucesso!", extra_tags='alert alert-success')
    except Exception as e:
        messages.error(request, f"Erro ao atualizar o status: {e}", extra_tags='alert alert-danger')

    # Redireciona de volta para a mesma página de detalhes do pedido
    return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

def detalhes_pedido(request, id_pedido):
    """
    Busca e exibe todas as informações detalhadas de um pedido específico,
    incluindo itens, pagamentos e valores calculados de forma segura.
    """
    # 1. Bloco de segurança
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.', extra_tags='alert alert-warning')
        return redirect('clientes:login')

    # Inicializa as variáveis para garantir que sempre existam
    pedido_info = None
    itens_do_pedido = []
    pagamentos_do_pedido = []
    total_pago = Decimal('0.00') # Usa Decimal para precisão financeira

    try:
        with connection.cursor() as cursor:
            # 2. Busca os dados principais do Pedido e o nome do Cliente
            cursor.execute("""
                SELECT 
                    p.Id_Pedido, p.Dt_Pedido, p.Prazo_Entrega, p.Status_pedido,
                    p.Vlr_Total_pedido, p.Observacao, c.Nome 
                FROM Pedido p
                JOIN Cliente c ON p.Id_Cliente = c.id_cliente
                WHERE p.Id_Pedido = %s
            """, [id_pedido])
            pedido_data = cursor.fetchone()

            if not pedido_data:
                messages.error(request, "Pedido não encontrado.", extra_tags='alert alert-danger')
                return redirect('clientes:home')
            
            # 3. Busca dos Itens do Pedido
            cursor.execute("""
                SELECT pr.Nome, pp.Qtde, pp.Vlr_Total_Produto
                FROM Pedido_Produto pp
                JOIN Produto pr ON pp.Id_Produto = pr.Id_Produto
                WHERE pp.Id_Pedido = %s
            """, [id_pedido])
            itens_do_pedido = cursor.fetchall()

            # 4. Lógica de Pagamentos segura, usando o nome correto da tabela 'pgto_pedido'
            try:
                # Tenta buscar o histórico de pagamentos
                cursor.execute(
                    "SELECT dt_pgto, observacao, vlr_pagamento FROM pgto_pedido WHERE id_pedido = %s ORDER BY dt_pgto",
                    [id_pedido]
                )
                pagamentos_do_pedido = cursor.fetchall()
                
                # Tenta somar os valores dos pagamentos
                cursor.execute(
                    "SELECT SUM(vlr_pagamento) FROM pgto_pedido WHERE id_pedido = %s",
                    [id_pedido]
                )
                total_pago_result = cursor.fetchone()
                
                # Converte o resultado para Decimal, ou usa 0 se não houver pagamentos
                if total_pago_result and total_pago_result[0] is not None:
                    total_pago = total_pago_result[0]
            
            except Exception as e:
                # Se der erro (ex: tabela pgto_pedido não existe), assume 0 e imprime um aviso no terminal
                print(f"Aviso: Não foi possível carregar os pagamentos. Erro: {e}")

    except Exception as e:
        messages.error(request, f"Erro ao carregar dados do pedido: {e}", extra_tags='alert alert-danger')
        return redirect('clientes:home')

    # 5. Monta o dicionário final com todos os dados para o template
    valor_total_pedido = pedido_data[4] if pedido_data[4] is not None else Decimal('0.00')
    valor_restante = valor_total_pedido - total_pago
    
    pedido_info = {
        'id_pedido': pedido_data[0], 
        'data_pedido': pedido_data[1], 
        'prazo_entrega': pedido_data[2],
        'status': pedido_data[3], 
        'valor_total': valor_total_pedido, 
        'observacao': pedido_data[5], 
        'nome_cliente': pedido_data[6],
        'total_pago': total_pago,          # Valor calculado
        'valor_restante': valor_restante   # Valor calculado
    }

    contexto = {
        'pedido': pedido_info,
        'itens': itens_do_pedido,
        'pagamentos': pagamentos_do_pedido,
    }
    
    return render(request, 'clientes/home.html', contexto)

def registrar_pagamento(request, id_pedido):
    if request.method != 'POST':
        return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado.')
        return redirect('clientes:login')

    # No seu formulário, o campo 'tipo_pagamento' será usado para a coluna 'observacao'
    observacao = request.POST.get('tipo_pagamento')
    valor_pago = request.POST.get('valor_pago')
    data_pagamento = request.POST.get('data_pagamento')

    if not valor_pago or not data_pagamento:
        messages.error(request, 'Data e Valor do pagamento são obrigatórios.', extra_tags='alert alert-danger')
        return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # CORREÇÃO: Usa os nomes corretos da tabela (pgto_pedido) e colunas (id_pedido, dt_pgto, etc.)
                cursor.execute(
                    """
                    INSERT INTO pgto_pedido (id_pedido, dt_pgto, vlr_pagamento, observacao)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [id_pedido, data_pagamento, valor_pago.replace(',', '.'), observacao]
                )
        
        messages.success(request, 'Pagamento registado com sucesso!', extra_tags='alert alert-success')

    except Exception as e:
        messages.error(request, f"Erro ao registar o pagamento: {e}", extra_tags='alert alert-danger')

    return redirect('clientes:detalhes_pedido', id_pedido=id_pedido)

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
                    # Verifica se CPF ou Email já existem
                    cursor.execute("SELECT 1 FROM usuario WHERE Cpf = %s OR Email = %s", [cpf, email])
                    if cursor.fetchone():
                        # Ajuste na mensagem de erro
                        messages.error(request, 'CPF ou E-mail já cadastrado no sistema.', extra_tags='alert alert-danger')
                        return render(request, 'clientes/cadastro.html', {'form': form})

                    senha_hash = make_password(senha)
                    cursor.execute(
                        "INSERT INTO usuario (Nome, Cpf, Email, Senha, Status) VALUES (%s, %s, %s, %s, %s)",
                        [nome, cpf, email, senha_hash, 'A']
                    )
                
                # --- INÍCIO DA ALTERAÇÃO NA MENSAGEM DE SUCESSO ---

                # Mensagem de sucesso com HTML para um visual mais rico
                mensagem_sucesso_html = """
                    <div class="d-flex align-items-center">
                        <i class="bi bi-check-circle-fill fs-4 me-3"></i>
                        <div>
                            <h5 class="alert-heading mb-1">Conta Criada com Sucesso!</h5>
                            Agora você já pode fazer o login com suas novas credenciais.
                        </div>
                    </div>
                """
                # Adiciona as classes do Bootstrap para garantir a cor verde e o comportamento de fechar
                messages.success(request, mensagem_sucesso_html, extra_tags='alert alert-success alert-dismissible fade show')
                
                # --- FIM DA ALTERAÇÃO ---

                return redirect('clientes:login')
            
            except Exception as e:
                # Ajuste na mensagem de erro
                messages.error(request, f'Ocorreu um erro no servidor: {e}', extra_tags='alert alert-danger')
                
        # Se o form não for válido, renderiza a página com o form que contém os erros
        return render(request, 'clientes/cadastro.html', {'form': form})
    
    # Se for um GET request
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
                
                return redirect('clientes:home')
            
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

def listar_clientes(request):
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.')
        return redirect('clientes:login')

    search_query = request.GET.get('search', '')
    order_by = request.GET.get('order_by', 'nome')
    colunas_permitidas = ['id_cliente', 'nome', 'cpf_cnpj', 'email', 'celular']
    if order_by.lower() not in colunas_permitidas:
        order_by = 'nome'

    print(f"--- DEBUG: INICIANDO LISTAGEM DE CLIENTES ---")
    print(f"--- DEBUG: Buscando por: '{search_query}' ---")
    
    try:
        with connection.cursor() as cursor:
            base_query = f"SELECT id_cliente, nome, cpf_cnpj, email, celular FROM cliente"
            params = []
            if search_query:
                base_query += " WHERE nome ILIKE %s OR cpf_cnpj ILIKE %s"
                params.extend(['%' + search_query + '%', '%' + search_query + '%'])
            
            base_query += f" ORDER BY {order_by}"
            cursor.execute(base_query, params)
            
            # Pega TODOS os resultados da query
            clientes_data = cursor.fetchall()
            
            # DEBUG: VAMOS VER SE O BANCO RETORNOU ALGO
            print(f"--- DEBUG: A query SQL retornou {len(clientes_data)} registos do banco. ---")

    except Exception as e:
        print(f"--- DEBUG: OCORREU UM ERRO NA QUERY SQL: {e} ---")
        messages.error(request, f"Ocorreu um erro ao buscar os clientes: {e}")
        clientes_data = []

    paginator = Paginator(clientes_data, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # DEBUG: VAMOS VER QUANTOS ITENS ESTÃO NA PÁGINA ATUAL
    print(f"--- DEBUG: O Paginator colocou {len(page_obj.object_list)} itens na página atual. ---")

    clientes_list = [
        {'id_cliente': c[0], 'nome': c[1], 'cpf_cnpj': c[2], 'email': c[3], 'celular': c[4]}
        for c in page_obj.object_list
    ]

    contexto = {
        'page_obj': page_obj, 
        'clientes': clientes_list,
        'order_by': order_by,
        'search_query': search_query,
    }

    return render(request, 'clientes/listar_clientes.html', contexto)

def adicionar_cliente(request):
    # Bloco de segurança manual para garantir que o usuário está logado
    if 'user_id' not in request.session:
        # Mensagem de aviso (amarela)
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.', extra_tags='alert alert-warning')
        return redirect('clientes:login')

    # Processa o formulário se for uma requisição POST
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        
        if form.is_valid():
            nome = form.cleaned_data['nome']
            cpf_cnpj = form.cleaned_data['cpf_cnpj']
            endereco = form.cleaned_data['endereco']
            telefone = form.cleaned_data['telefone']
            celular = form.cleaned_data['celular']
            email = form.cleaned_data['email']

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # Verifica se já existe um cliente com esse CPF/CNPJ
                        cursor.execute("SELECT 1 FROM cliente WHERE cpf_cnpj = %s", [cpf_cnpj])
                        if cursor.fetchone():
                            # Mensagem de erro (vermelha)
                            messages.error(request, "Já existe um cliente cadastrado com este CPF/CNPJ.", extra_tags='alert alert-danger')
                            return render(request, 'clientes/adicionar_cliente.html', {'form': form})
                        
                        # Se não existir, insere o novo cliente
                        cursor.execute(
                            """
                            INSERT INTO cliente (nome, cpf_cnpj, endereco, telefone, celular, email)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            [nome, cpf_cnpj, endereco, telefone, celular, email]
                        )
                
                # Mensagem de sucesso (verde) e com animação para fechar
                messages.success(request, "Cliente adicionado com sucesso!", extra_tags='alert alert-success alert-dismissible fade show')
                return redirect('clientes:home')

            except Exception as e:
                # Mensagem de erro (vermelha) em caso de falha no banco
                messages.error(request, f"Erro ao cadastrar o cliente: {e}", extra_tags='alert alert-danger')
                return render(request, 'clientes/adicionar_cliente.html', {'form': form})
        
        # Se o formulário não for válido, renderiza a página novamente com os erros
        # O próprio 'form.errors' será exibido no template
        return render(request, 'clientes/adicionar_cliente.html', {'form': form})

    # Se for uma requisição GET, apenas exibe um formulário em branco
    else:
        form = ClienteForm()
    
    return render(request, 'clientes/adicionar_cliente.html', {'form': form})

def visualizar_cliente(request, id_cliente):
    # 1. Verificação de segurança primeiro
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.')
        return redirect('clientes:login')
    
    try:
        with connection.cursor() as cursor:
            # 2. Busca os dados completos do cliente específico
            cursor.execute(
                "SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM cliente WHERE id_cliente = %s", 
                [id_cliente]
            )
            cliente_data = cursor.fetchone()

    except Exception as e:
        # Se houver um erro de banco de dados, avisa e redireciona
        messages.error(request, f"Erro ao aceder ao banco de dados: {e}", extra_tags='alert alert-danger')
        return redirect('clientes:listar_clientes')

    # 3. Verifica se o cliente foi encontrado DEPOIS da busca
    if not cliente_data:
        messages.error(request, "Cliente não encontrado.", extra_tags='alert alert-danger')
        return redirect('clientes:listar_clientes')
    
    # 4. Se tudo correu bem, prepara os dados para o template
    cliente_dict = {
        'id_cliente': cliente_data[0], 
        'nome': cliente_data[1], 
        'cpf_cnpj': cliente_data[2],
        'endereco': cliente_data[3], 
        'telefone': cliente_data[4], 
        'celular': cliente_data[5],
        'email': cliente_data[6]
    }

    # (Opcional) Busca de pedidos do cliente aqui, se necessário

    contexto = {
        'cliente': cliente_dict,
        # 'pedidos': ...,
    }
    
    # 5. O retorno final, que sempre será executado em caso de sucesso
    return render(request, 'clientes/visualizar_cliente.html', contexto)

def editar_cliente(request, id_cliente):
    # Bloco de segurança manual
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para aceder a esta página.', extra_tags='alert alert-warning')
        return redirect('clientes:login')

    # Busca os dados iniciais do cliente
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_cliente, nome, cpf_cnpj, endereco, telefone, celular, email FROM cliente WHERE id_cliente = %s", [id_cliente])
            cliente_data = cursor.fetchone()

            if not cliente_data:
                # CORREÇÃO: Adicionada extra_tags de erro
                messages.error(request, "Cliente não encontrado.", extra_tags='alert alert-danger')
                return redirect('clientes:listar_clientes')

            cliente_dict = {
                'id_cliente': cliente_data[0], 'nome': cliente_data[1], 'cpf_cnpj': cliente_data[2],
                'endereco': cliente_data[3], 'telefone': cliente_data[4], 'celular': cliente_data[5],
                'email': cliente_data[6]
            }
    except Exception as e:
        messages.error(request, f"Erro ao buscar cliente: {e}", extra_tags='alert alert-danger')
        return redirect('clientes:listar_clientes')

    # Se o formulário for enviado
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # Verificação de duplicidade para outros clientes
                        cpf_cnpj = form.cleaned_data['cpf_cnpj']
                        cursor.execute("SELECT 1 FROM cliente WHERE cpf_cnpj = %s AND id_cliente != %s", [cpf_cnpj, id_cliente])
                        if cursor.fetchone():
                            # CORREÇÃO: Adicionada extra_tags de erro
                            messages.error(request, "Este CPF/CNPJ já pertence a outro cliente.", extra_tags='alert alert-danger')
                            return render(request, 'clientes/editar_cliente.html', {'form': form, 'cliente': cliente_dict})

                        # Atualiza os dados no banco
                        cursor.execute(
                            """
                            UPDATE cliente SET nome=%s, cpf_cnpj=%s, endereco=%s, telefone=%s, celular=%s, email=%s 
                            WHERE id_cliente=%s
                            """,
                            [
                                form.cleaned_data['nome'], form.cleaned_data['cpf_cnpj'],
                                form.cleaned_data['endereco'], form.cleaned_data['telefone'],
                                form.cleaned_data['celular'], form.cleaned_data['email'],
                                id_cliente
                            ]
                        )
                
                # --- AQUI ESTÁ A CORREÇÃO PRINCIPAL ---
                # CORREÇÃO: Adicionada extra_tags de sucesso
                messages.success(request, "Cliente atualizado com sucesso!", extra_tags='alert alert-success alert-dismissible fade show')
                return redirect('clientes:listar_clientes')

            except Exception as e:
                messages.error(request, f"Erro ao atualizar cliente: {e}", extra_tags='alert alert-danger')
    else:
        # Se for GET, preenche o formulário com os dados existentes
        form = ClienteForm(initial=cliente_dict)

    return render(request, 'clientes/editar_cliente.html', {'form': form, 'cliente': cliente_dict})

def excluir_cliente(request, cliente_id):
    if 'user_id' not in request.session:
        messages.warning(request, 'Você precisa estar logado para executar esta ação.')
        return redirect('clientes:login')

    if request.method == "POST":
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM cliente WHERE id_cliente = %s", [cliente_id])
                
                # AQUI ESTÁ A MENSAGEM QUE SERÁ EXIBIDA
                # Garanta que as extra_tags estão corretas para a cor verde e para o botão de fechar
                messages.success(request, "Cliente excluído com sucesso!", extra_tags='alert alert-success alert-dismissible fade show')

        except Exception as e:
            messages.error(request, f"Erro ao excluir o cliente: {str(e)}", extra_tags='alert alert-danger')

    return redirect('clientes:listar_clientes')

def limpar_mensagens(request):
    storage = get_messages(request)
    for _ in storage:
        pass
    return JsonResponse({"status": "ok"})