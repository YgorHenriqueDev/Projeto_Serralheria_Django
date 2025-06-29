from django import forms
from validate_docbr import CPF, CNPJ

class ClienteForm(forms.Form):
    # Para cada campo, adicionamos o 'widget' para definir os atributos HTML
    
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
        max_length=18,  # Aumentado para acomodar máscaras (ex: xx.xxx.xxx/xxxx-xx)
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
        required=False, # Não obrigatório
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
        widget=forms.EmailInput(attrs={ # Usando EmailInput para validação de email no HTML5
            'class': 'form-control form-control-lg',
            'placeholder': 'email@exemplo.com'
        })
    )
    
    # Sua função de validação continua perfeita, sem alterações necessárias.
    def clean_cpf_cnpj(self):
        cpf_cnpj = self.cleaned_data['cpf_cnpj'].replace('.', '').replace('-', '').replace('/', '')

        if not cpf_cnpj.isdigit():
            raise forms.ValidationError("O CPF ou CNPJ deve conter apenas números.")

        if len(cpf_cnpj) == 11:
            if not CPF().validate(cpf_cnpj):
                raise forms.ValidationError("CPF inválido.")
        elif len(cpf_cnpj) == 14:
            if not CNPJ().validate(cpf_cnpj):
                raise forms.ValidationError("CNPJ inválido.")
        else:
            raise forms.ValidationError("O tamanho do CPF ou CNPJ informado é inválido.")

        return self.cleaned_data['cpf_cnpj'] # Retorna o valor original com máscara, se houver


class UsuarioForm(forms.Form):
    nome = forms.CharField(label="Nome Completo", required=True)
    cpf = forms.CharField(label="CPF", required=True)
    email = forms.EmailField(label="E-mail", required=True)
    senha = forms.CharField(label="Senha", required=True, widget=forms.PasswordInput)
    confirmar_senha = forms.CharField(label="Confirme a Senha", required=True, widget=forms.PasswordInput)

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            cpf_numeros = "".join(filter(str.isdigit, cpf))
            if not CPF().validate(cpf_numeros):
                raise forms.ValidationError("Este número de CPF é inválido.")
            return cpf_numeros
        return cpf

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("senha")
        confirmar_senha = cleaned_data.get("confirmar_senha")
        if senha and confirmar_senha and senha != confirmar_senha:
            raise forms.ValidationError("As senhas digitadas não conferem.")
        return cleaned_data