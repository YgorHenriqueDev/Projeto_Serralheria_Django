from django import forms
from validate_docbr import CPF, CNPJ

class ClienteForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=150, required=True)
    cpf_cnpj = forms.CharField(label="CPF/CNPJ", max_length=14, required=True)
    endereco = forms.CharField(label="Endereço", max_length=150, required=True)
    telefone = forms.CharField(label="Telefone", max_length=20, required=False)
    celular = forms.CharField(label="Celular", max_length=20, required=True)
    email = forms.EmailField(label="E-mail", max_length=150, required=True)
    

    def clean_cpf_cnpj(self):
        cpf_cnpj = self.cleaned_data['cpf_cnpj'].replace('.', '').replace('-', '').replace('/', '')  # Remove caracteres especiais

        if cpf_cnpj.isdigit():  # Confirma que contém apenas números
            if len(cpf_cnpj) == 11:  # CPF
                if not CPF().validate(cpf_cnpj):
                    raise forms.ValidationError("CPF inválido.")
            elif len(cpf_cnpj) == 14:  # CNPJ
                if not CNPJ().validate(cpf_cnpj):
                    raise forms.ValidationError("CNPJ inválido.")
            else:
                raise forms.ValidationError("O CPF ou CNPJ informado é inválido.")
        else:
            raise forms.ValidationError("O CPF ou CNPJ deve conter apenas números.")

        return cpf_cnpj

class UsuarioForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=150, required=True)
    cpf = forms.CharField(label="CPF", max_length=14, required=True)
    email = forms.EmailField(label="E-mail", max_length=50, required=True)
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput(), max_length=100, required=True)
    status = forms.CharField(label="Status", max_length=1, required=True)
