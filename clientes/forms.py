from django import forms
from validate_docbr import CPF, CNPJ
import re

class ClienteForm(forms.Form):
    # Seus campos estão perfeitamente definidos, nenhuma alteração necessária aqui.
    nome = forms.CharField(
        label="Nome", 
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': 'Nome completo ou Razão Social'
        })
    )
    cpf_cnpj = forms.CharField(
        label="CPF/CNPJ", 
        max_length=18,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Digite o CPF ou CNPJ'
        })
    )
    endereco = forms.CharField(
        label="Endereço", 
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Rua, Número, Bairro, Cidade - Estado'
        })
    )
    telefone = forms.CharField(
        label="Telefone", 
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '(Opcional)'
        })
    )
    celular = forms.CharField(
        label="Celular", 
        max_length=20, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '(xx) xxxxx-xxxx'
        })
    )
    email = forms.EmailField(
        label="E-mail", 
        max_length=150, 
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'email@exemplo.com'
        })
    )
    
    # --- MÉTODO DE VALIDAÇÃO AJUSTADO ---
    def clean_cpf_cnpj(self):
        cpf_cnpj = self.cleaned_data.get('cpf_cnpj')

        # 1. Limpeza de dados mais eficiente: remove QUALQUER caractere que não seja um dígito.
        numeros = "".join(filter(str.isdigit, cpf_cnpj))

        # Valida o tamanho e o tipo (CPF ou CNPJ)
        if len(numeros) == 11:
            if not CPF().validate(numeros):
                raise forms.ValidationError("O número de CPF informado é inválido.")
        elif len(numeros) == 14:
            if not CNPJ().validate(numeros):
                raise forms.ValidationError("O número de CNPJ informado é inválido.")
        else:
            raise forms.ValidationError("O CPF/CNPJ deve conter 11 ou 14 dígitos.")

        # 2. MUDANÇA MAIS IMPORTANTE: Retorna a versão limpa (apenas números).
        return numeros


# --- VERSÃO ATUALIZADA DO SEU FORMULÁRIO DE USUÁRIO ---
class UsuarioForm(forms.Form):
    nome = forms.CharField(
        label="Nome Completo", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Seu nome completo', 'autocomplete': 'off'})
    )
    cpf = forms.CharField(
        label="CPF", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Digite seu CPF', 'autocomplete': 'off'})
    )
    email = forms.EmailField(
        label="E-mail", 
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'seu.email@exemplo.com', 'autocomplete': 'off'})
    )
    senha = forms.CharField(
        label="Senha", 
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Crie uma senha forte', 'autocomplete': 'new-password'})
    )
    confirmar_senha = forms.CharField(
        label="Confirme a Senha", 
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Repita a senha', 'autocomplete': 'new-password'})
    )

    # 2. MÉTODO ADICIONADO PARA VALIDAR A FORÇA DA SENHA
    def clean_senha(self):
        senha = self.cleaned_data.get('senha')
        errors = []
        if len(senha) < 8:
            errors.append("A senha deve conter pelo menos 8 caracteres.")
        if not re.search(r'[A-Z]', senha):
            errors.append("A senha deve conter pelo menos uma letra maiúscula.")
        if not re.search(r'[a-z]', senha):
            errors.append("A senha deve conter pelo menos uma letra minúscula.")
        if not re.search(r'[0-9]', senha):
            errors.append("A senha deve conter pelo menos um número.")
        if not re.search(r'[^A-Za-z0-9]', senha): # Verifica se há um caractere que NÃO é letra ou número
            errors.append("A senha deve conter pelo menos um caractere especial (!@#$...).")

        if errors:
            # Se houver erros, lança uma única ValidationError com a lista de todos os problemas
            raise forms.ValidationError(errors)
        
        return senha

    # Validação de senhas (verifica se são iguais)
    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("senha")
        confirmar_senha = cleaned_data.get("confirmar_senha")
        if senha and confirmar_senha and senha != confirmar_senha:
            raise forms.ValidationError("As senhas digitadas não conferem.")
        return cleaned_data

    # Validação de CPF
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            cpf_numeros = "".join(filter(str.isdigit, cpf))
            if len(cpf_numeros) != 11:
                raise forms.ValidationError("O CPF deve conter 11 dígitos.")
            if not CPF().validate(cpf_numeros):
                raise forms.ValidationError("Este número de CPF é inválido.")
            return cpf_numeros
        return cpf

        
class PedidoForm(forms.Form):
    """
    Formulário para os dados gerais de um pedido (criação e edição),
    incluindo a lógica para popular o dropdown de clientes dinamicamente.
    """
    cliente = forms.ChoiceField(
        label="Cliente", 
        required=True,
        widget=forms.Select(attrs={'class': 'form-select form-control-lg'})
    )
    data_pedido = forms.DateField(
        label="Data do Pedido", 
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg', 'type': 'date'})
    )
    prazo_entrega = forms.DateField(
        label="Prazo de Entrega",
        required=False, # Este campo não é obrigatório
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg', 'type': 'date'})
    )
    observacao = forms.CharField(
        label="Observação",
        required=False, # Este campo também não é obrigatório
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalhes do pedido, medidas, etc.'})
    )

    def __init__(self, *args, **kwargs):
        """
        Construtor customizado para aceitar uma lista de clientes da view
        e usá-la para preencher as opções do campo 'cliente'.
        """
        # "Apanha" o argumento 'clientes' que a view enviou
        clientes_choices = kwargs.pop('clientes', [])
        
        # Chama o construtor original da classe pai
        super(PedidoForm, self).__init__(*args, **kwargs)
        
        # Usa a lista de clientes para definir as opções (choices) do dropdown
        self.fields['cliente'].choices = [('', 'Selecione um cliente...')] + clientes_choices