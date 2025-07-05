# clientes/urls.py

from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    # URLs de Autenticação e Páginas Principais
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro, name='cadastro'),
    
    # URLs para gerir Clientes (CRUD)
    path('clientes/', views.listar_clientes, name='listar_clientes'),
    path('clientes/adicionar/', views.adicionar_cliente, name='adicionar_cliente'),
    path('clientes/<int:id_cliente>/', views.visualizar_cliente, name='visualizar_cliente'),
    path('clientes/<int:id_cliente>/editar/', views.editar_cliente, name='editar_cliente'),
    path('clientes/<int:cliente_id>/excluir/', views.excluir_cliente, name='excluir_cliente'),
    
    # URLs para gerir Pedidos (CRUD)
    path('pedidos/novo/', views.novo_pedido_view, name='novo_pedido'),
    path('pedidos/<int:id_pedido>/', views.detalhes_pedido, name='detalhes_pedido'),
    path('pedidos/<int:id_pedido>/editar/', views.editar_pedido_view, name='editar_pedido'),
    
    # URLs para Ações Específicas
    path('pedidos/<int:id_pedido>/registrar_pagamento/', views.registrar_pagamento, name='registrar_pagamento'),
    path('pedidos/<int:id_pedido>/atualizar_status/', views.atualizar_status_pedido, name='atualizar_status_pedido'),
]