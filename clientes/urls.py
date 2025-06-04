from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    # URLs de autenticação
    path('', views.login_view, name='login'),  # Tela de login
    path('logout/', views.logout_view, name='logout'),  # Logout do usuário
    path('cadastro/', views.cadastro, name='cadastro'),

    # URLs de clientes
    path('listar_clientes/', views.listar_clientes, name='listar_clientes'),  # Listar clientes
    path('adicionar_cliente/', views.adicionar_cliente, name='adicionar_cliente'),  # Adicionar cliente
    path('editar_cliente/<int:id_cliente>/', views.editar_cliente, name='editar_cliente'),  # Editar cliente
    path('excluir_cliente/<int:cliente_id>/', views.excluir_cliente, name='excluir_cliente'),  # Excluir cliente
    path('visualizar/<int:id_cliente>/', views.visualizar_cliente, name='visualizar_cliente'), # Visualizer cliente
    path("limpar-mensagens/", views.limpar_mensagens, name="limpar_mensagens"), # Para limpar menagen
]
